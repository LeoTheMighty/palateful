"""Tests for invite link endpoints."""

from conftest import MockInviteLink, MockRecipeBook


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
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser
        from conftest import MockRecipeBookUser

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "recipe_book",
                "resource_id": book_id,
                "role": "viewer",
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
        link = MockInviteLink(
            token=token,
            resource_type="recipe_book",
            resource_id="test-book-id",
            created_by_id=str(mock_user.id),
        )
        book = MockRecipeBook(id="test-book-id", name="Shared Book")

        from utils.models.invite_link import InviteLink
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(InviteLink, link, token=token)
        mock_db.set_find_by(RecipeBook, book, id="test-book-id")

        response = client.get(f"/v1/invite-links/{token}")
        assert response.status_code == 200


class TestDeactivateInviteLink:
    """Tests for DELETE /v1/invite-links/{invite_link_id}."""

    def test_deactivate_invite_link_not_found(self, client, mock_db, mock_user):
        """Test deactivating a nonexistent link."""
        response = client.delete("/v1/invite-links/nonexistent")
        assert response.status_code in (404, 500)
