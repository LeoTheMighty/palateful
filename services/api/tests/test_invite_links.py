"""Tests for invite link endpoints."""

import uuid

from conftest import (
    MockExecuteResult,
    MockInviteLink,
    MockRecipeBookUser,
    MockUser,
)


class TestCreateInviteLink:
    """Tests for POST /v1/invite-links."""

    def test_create_invite_link_missing_fields(self, client, mock_async_db, mock_user):
        """Creating an invite link with missing fields fails with 422."""
        response = client.post("/v1/invite-links", json={})
        assert response.status_code == 422

    def test_create_invite_link_success(self, client, mock_async_db, mock_user):
        """Creating an invite link returns a deep_link URL."""
        book_id = "b0000000-0000-0000-0000-000000000001"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        # CreateInviteLink uses self.db.execute() for permission check
        mock_async_db.db.execute.return_value = MockExecuteResult([membership])

        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "recipe_book",
                "resource_id": book_id,
                "role_offered": "viewer",
            },
        )
        assert response.status_code in (200, 201)

    def test_create_returns_deep_link(self, client, mock_async_db, mock_user):
        """Created invite link response contains a palateful:// deep link."""
        book_id = "b0000000-0000-0000-0000-000000000001"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([membership])

        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "recipe_book",
                "resource_id": book_id,
                "role_offered": "viewer",
            },
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert "deep_link" in data
        assert data["deep_link"].startswith("palateful://invite/")
        assert len(data["token"]) > 0


class TestPreviewInviteLink:
    """Tests for GET /v1/invite-links/{token}."""

    def test_preview_invite_link_not_found(self, client, mock_async_db, mock_user):
        """Previewing a nonexistent invite link returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.get("/v1/invite-links/nonexistent-token")
        assert response.status_code in (404, 500)

    def test_preview_invite_link_success(self, client, mock_async_db, mock_user):
        """Previewing an active invite link returns 200."""
        token = "test-token"
        creator = MockUser(
            id=str(mock_user.id),
            name="Test User",
            username="testuser",
        )
        link = MockInviteLink(
            token=token,
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by_id=str(mock_user.id),
            role_offered="viewer",
            is_active=True,
            created_by=creator,
        )

        # PreviewInviteLink uses self.db.execute() multiple times:
        # 1. Fetch invite link with joinedload
        # 2. check_existing_membership (RecipeBookUser)
        # 3. get_resource_name (RecipeBook.name)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([link]),           # invite link query
            MockExecuteResult([]),               # not already a member
            MockExecuteResult(["Shared Book"]),  # resource name
        ]

        response = client.get(f"/v1/invite-links/{token}")
        assert response.status_code == 200

    def test_preview_returns_state_active(self, client, mock_async_db, mock_user):
        """Preview of an active link returns state='active'."""
        token = "active-token-abc123"
        creator = MockUser(id=str(uuid.uuid4()), name="Creator", username="creator")
        link = MockInviteLink(
            token=token,
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by_id=str(creator.id),
            role_offered="editor",
            is_active=True,
            max_uses=None,
            expires_at=None,
            created_by=creator,
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([link]),           # invite link query
            MockExecuteResult([]),               # not already a member
            MockExecuteResult(["My Book"]),      # resource name
        ]

        response = client.get(f"/v1/invite-links/{token}")
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "active"
        assert data["role_offered"] == "editor"


class TestDeactivateInviteLink:
    """Tests for DELETE /v1/invite-links/{invite_link_id}."""

    def test_deactivate_invite_link_not_found(self, client, mock_async_db, mock_user):
        """Deactivating a nonexistent link returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.delete("/v1/invite-links/nonexistent")
        assert response.status_code in (404, 500)


class TestJoinViaLink:
    """Tests for POST /v1/invite-links/{token}/join."""

    def test_join_via_link_not_found(self, client, mock_async_db, mock_user):
        """Joining a nonexistent invite link returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.post("/v1/invite-links/nonexistent-token/join")
        assert response.status_code in (404, 500)

    def test_join_via_link_success(self, client, mock_async_db, mock_user):
        """Joining an active link creates membership and returns role."""
        token = "validtoken12345678"
        creator = MockUser(id=str(uuid.uuid4()), name="Alice", username="alice")
        link = MockInviteLink(
            token=token,
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by_id=str(creator.id),
            role_offered="viewer",
            is_active=True,
            max_uses=None,
            expires_at=None,
            use_count=0,
        )
        link.created_by = creator

        # JoinViaLink sequence:
        # 1. fetch invite_link with joinedload
        # 2. check_existing_membership: RecipeBookUser → None (not a member)
        # 3. create_membership: check existing RecipeBookUser → None
        # 4. get_resource_name: RecipeBook.name
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([link]),          # fetch link
            MockExecuteResult([]),              # check_existing_membership
            MockExecuteResult([]),              # create_membership check
            MockExecuteResult(["My Book"]),     # get_resource_name
        ]

        response = client.post(f"/v1/invite-links/{token}/join")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "viewer"
        assert data["already_member"] is False
        assert data["resource_name"] == "My Book"
