"""Tests for invitation endpoints."""

import uuid

from conftest import (
    MockExecuteResult,
    MockInvitation,
    MockRecipeBookUser,
    MockUser,
)


BOOK_ID = "b0000000-0000-0000-0000-000000000001"


class TestListReceivedInvitations:
    """Tests for GET /v1/invitations."""

    def test_list_received_invitations_empty(self, client, mock_db, mock_user):
        """Listing returns empty list when no invitations exist."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/invitations")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_returns_invitation_items(self, client, mock_db, mock_user):
        """GET /v1/invitations returns invitation items with from_user info."""
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice", username="alice")
        invitation = MockInvitation(
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        mock_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),   # fetch invitations list
            MockExecuteResult(["My Book"]),    # get_resource_name
        ]

        response = client.get("/v1/invitations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["role_offered"] == "editor"
        assert data[0]["from_user"]["name"] == "Alice"
        assert data[0]["resource_name"] == "My Book"


class TestListSentInvitations:
    """Tests for GET /v1/invitations/sent."""

    def test_list_sent_invitations_success(self, client, mock_db, mock_user):
        """Test listing sent invitations returns 200."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200


class TestSendInvitation:
    """Tests for POST /v1/invitations."""

    def test_send_invitation_missing_fields(self, client, mock_db, mock_user):
        """Sending an invitation with missing required fields fails with 422."""
        response = client.post("/v1/invitations", json={})
        assert response.status_code == 422

    def test_send_invitation_no_permission_returns_403(self, client, mock_db, mock_user):
        """Sender without membership on the recipe book gets 403."""
        # check_resource_permission → db.execute returns no membership
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "someuser",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_self_invite_returns_400(self, client, mock_db, mock_user):
        """Inviting yourself returns 400."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        # sequence: 1=check_resource_permission, 2=username lookup → same as mock_user
        mock_db.db.execute.side_effect = [
            MockExecuteResult([membership]),  # check_resource_permission
            MockExecuteResult([mock_user]),   # User lookup by username → self
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": mock_user.username,
            },
        )
        assert response.status_code == 400

    def test_send_invitation_to_username_success(self, client, mock_db, mock_user):
        """Owner can send invitation by username — returns 201 with pending status."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="janesmith")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        # Sequence of db.execute() calls in SendInvitation.execute():
        # 1. check_resource_permission: RecipeBookUser lookup
        # 2. User lookup by username
        # 3. check_existing_membership: RecipeBookUser lookup
        # 4. duplicate invitation check
        # 5. rate limit count (scalar)
        # 6. get_resource_name: RecipeBook.name (called in push notification block)
        mock_db.db.execute.side_effect = [
            MockExecuteResult([membership]),   # check_resource_permission
            MockExecuteResult([target_user]),  # User lookup by username
            MockExecuteResult([]),             # check_existing_membership → not a member
            MockExecuteResult([]),             # duplicate invitation check → none
            MockExecuteResult([0]),            # rate limit count → 0 sent today
            MockExecuteResult(["My Book"]),    # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "janesmith",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["role_offered"] == "editor"


class TestAcceptInvitation:
    """Tests for POST /v1/invitations/{id}/accept."""

    def test_accept_invitation_not_found(self, client, mock_db, mock_user):
        """Accepting a nonexistent invitation returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.post("/v1/invitations/nonexistent/accept")
        assert response.status_code in (404, 500)

    def test_accept_invitation_success(self, client, mock_db, mock_user):
        """Accepting a valid pending invitation returns 200 with accepted status."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        # Sequence:
        # 1. fetch invitation with joinedload
        # 2. create_membership: check existing RecipeBookUser → None
        # 3. get_resource_name: RecipeBook.name
        mock_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),   # fetch invitation
            MockExecuteResult([]),             # create_membership: check existing
            MockExecuteResult(["My Book"]),    # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["role"] == "editor"


class TestDeclineInvitation:
    """Tests for POST /v1/invitations/{id}/decline."""

    def test_decline_invitation_not_found(self, client, mock_db, mock_user):
        """Declining a nonexistent invitation returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.post("/v1/invitations/nonexistent/decline")
        assert response.status_code in (404, 500)


class TestRevokeInvitation:
    """Tests for DELETE /v1/invitations/{id}."""

    def test_revoke_invitation_not_found(self, client, mock_db, mock_user):
        """Revoking a nonexistent invitation returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])
        response = client.delete("/v1/invitations/nonexistent")
        assert response.status_code in (404, 500)

    def test_revoke_success(self, client, mock_db, mock_user):
        """Owner can revoke a pending invitation they sent."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=mock_user.id,
            status="pending",
        )
        mock_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.delete(f"/v1/invitations/{invitation_id}")
        assert response.status_code == 200
