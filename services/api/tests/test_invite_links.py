"""Tests for invite link endpoints."""

from conftest import (
    MockExecuteResult,
    MockInviteLink,
    MockRecipeBookUser,
    MockUser,
)


class TestCreateInviteLink:
    """Tests for POST /v1/invite-links."""

    def test_create_invite_link_missing_fields(self, client, mock_db, mock_user):
        """Test creating an invite link with missing fields fails."""
        response = client.post(
            "/v1/invite-links",
            json={}
        )
        assert response.status_code == 422

    def test_create_invite_link_success(self, client, mock_db, mock_user):
        """Test creating an invite link."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        # CreateInviteLink uses self.db.execute() for permission check
        mock_db.db.execute.return_value = MockExecuteResult([membership])

        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "recipe_book",
                "resource_id": book_id,
                "role_offered": "viewer",
            }
        )
        assert response.status_code in (200, 201)


class TestPreviewInviteLink:
    """Tests for GET /v1/invite-links/{token}."""

    def test_preview_invite_link_not_found(self, client, mock_db, mock_user):
        """Test previewing a nonexistent invite link."""
        response = client.get("/v1/invite-links/nonexistent-token")
        assert response.status_code in (404, 500)

    def test_preview_invite_link_success(self, client, mock_db, mock_user):
        """Test previewing an invite link."""
        token = "test-token"
        creator = MockUser(
            id=str(mock_user.id),
            name="Test User",
            username="testuser",
        )
        link = MockInviteLink(
            token=token,
            resource_type="recipe_book",
            resource_id="test-book-id",
            created_by_id=str(mock_user.id),
            role_offered="viewer",
            is_active=True,
            created_by=creator,
        )

        # PreviewInviteLink uses self.db.execute() multiple times:
        # 1. Fetch invite link with joinedload
        # 2. check_existing_membership (RecipeBookUser)
        # 3. get_resource_name (RecipeBook.name)
        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),          # invite link query
            MockExecuteResult([]),              # not already a member
            MockExecuteResult(["Shared Book"]), # resource name
        ]

        response = client.get(f"/v1/invite-links/{token}")
        assert response.status_code == 200


class TestDeactivateInviteLink:
    """Tests for DELETE /v1/invite-links/{invite_link_id}."""

    def test_deactivate_invite_link_not_found(self, client, mock_db, mock_user):
        """Test deactivating a nonexistent link."""
        response = client.delete("/v1/invite-links/nonexistent")
        assert response.status_code in (404, 500)
