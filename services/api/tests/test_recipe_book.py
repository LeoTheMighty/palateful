"""Tests for recipe book endpoints."""

from unittest.mock import MagicMock

from conftest import (
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
)


class TestListRecipeBooks:
    """Tests for GET /v1/recipe-books."""

    def test_list_recipe_books_success(self, client, mock_db, mock_user):
        """Test listing recipe books."""
        book = MockRecipeBook()
        # Query now returns (RecipeBook, recipe_count, user_role, member_count) tuples
        mock_db.db.query.return_value = MockQuery([(book, 3, "owner", 1)])

        response = client.get("/v1/recipe-books")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_recipe_books_empty(self, client, mock_db, mock_user):
        """Test listing when user has no recipe books."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/recipe-books")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestCreateRecipeBook:
    """Tests for POST /v1/recipe-books."""

    def test_create_recipe_book_success(self, client, mock_db, mock_user):
        """Test creating a recipe book."""
        response = client.post(
            "/v1/recipe-books",
            json={"name": "My New Book", "description": "A test book"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My New Book"
        assert data["description"] == "A test book"
        assert data["recipe_count"] == 0

    def test_create_recipe_book_no_description(self, client, mock_db, mock_user):
        """Test creating a recipe book without description."""
        response = client.post(
            "/v1/recipe-books",
            json={"name": "Minimal Book"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Book"
        assert data["description"] is None

    def test_create_recipe_book_missing_name(self, client):
        """Test creating a recipe book without name fails."""
        response = client.post(
            "/v1/recipe-books",
            json={"description": "No name"}
        )
        assert response.status_code == 422


class TestGetRecipeBook:
    """Tests for GET /v1/recipe-books/{id}."""

    def test_get_recipe_book_success(self, client, mock_db, mock_user):
        """Test getting a recipe book the user has access to."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe import Recipe

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        # Two db.query calls: recipes and members — both return empty
        mock_db.db.query.side_effect = [MockQuery([]), MockQuery([])]

        response = client.get(f"/v1/recipe-books/{book_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == book_id
        assert data["name"] == book.name
        assert "is_public" in data

    def test_get_recipe_book_access_denied(self, client, mock_db, mock_user):
        """Test getting a recipe book without access."""
        response = client.get("/v1/recipe-books/no-access-id")
        assert response.status_code == 403

    def test_get_recipe_book_with_recipes(self, client, mock_db, mock_user):
        """Test getting a recipe book that contains recipes."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        recipe = MockRecipe(recipe_book_id=book_id, name="Pasta")

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe import Recipe

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        # Two db.query calls: recipes (returns [recipe]) then members (returns [])
        mock_db.db.query.side_effect = [MockQuery([recipe]), MockQuery([])]

        response = client.get(f"/v1/recipe-books/{book_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["recipe_count"] == 1
        assert len(data["recipes"]) == 1
        assert data["recipes"][0]["name"] == "Pasta"


class TestUpdateRecipeBook:
    """Tests for PUT /v1/recipe-books/{id}."""

    def test_update_recipe_book_name(self, client, mock_db, mock_user):
        """Test updating recipe book name."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.db.query.return_value = MockQuery([5])

        response = client.put(
            f"/v1/recipe-books/{book_id}",
            json={"name": "Updated Name"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_recipe_book_is_public_owner(self, client, mock_db, mock_user):
        """Test that owner can toggle is_public."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id, is_public=False)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.db.query.return_value = MockQuery([0])

        response = client.put(
            f"/v1/recipe-books/{book_id}",
            json={"is_public": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_public"] is True

    def test_update_recipe_book_is_public_editor_denied(self, client, mock_db, mock_user):
        """Test that editor cannot toggle is_public."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor"
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.put(
            f"/v1/recipe-books/{book_id}",
            json={"is_public": True}
        )
        assert response.status_code == 403

    def test_update_recipe_book_access_denied(self, client, mock_db, mock_user):
        """Test updating without access fails."""
        response = client.put(
            "/v1/recipe-books/no-access-id",
            json={"name": "Updated"}
        )
        assert response.status_code == 403


class TestDeleteRecipeBook:
    """Tests for DELETE /v1/recipe-books/{id}."""

    def test_delete_recipe_book_success(self, client, mock_db, mock_user):
        """Test deleting a recipe book as owner."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.delete(f"/v1/recipe-books/{book_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_recipe_book_not_owner(self, client, mock_db, mock_user):
        """Test that non-owner cannot delete."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor"
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/recipe-books/{book_id}")
        assert response.status_code == 403

    def test_delete_recipe_book_no_access(self, client, mock_db, mock_user):
        """Test deleting without any access fails."""
        response = client.delete("/v1/recipe-books/no-access-id")
        assert response.status_code == 403


class TestArchiveRecipeBook:
    """Tests for POST /v1/recipe-books/{id}/archive."""

    def test_archive_recipe_book_success(self, client, mock_db, mock_user):
        """Test archiving a recipe book as owner."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id, include_archived=True)

        response = client.post(f"/v1/recipe-books/{book_id}/archive")
        assert response.status_code == 200
        assert book.archived_at is not None

    def test_archive_recipe_book_not_owner(self, client, mock_db, mock_user):
        """Test that non-owner cannot archive."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/recipe-books/{book_id}/archive")
        assert response.status_code == 403

    def test_archive_recipe_book_not_found(self, client, mock_db, mock_user):
        """Test archiving nonexistent book."""
        book_id = "nonexistent"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/recipe-books/{book_id}/archive")
        assert response.status_code == 404

    def test_archive_recipe_book_already_archived(self, client, mock_db, mock_user):
        """Test archiving an already archived book."""
        from datetime import UTC, datetime

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id, archived_at=datetime.now(UTC))
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id, include_archived=True)

        response = client.post(f"/v1/recipe-books/{book_id}/archive")
        assert response.status_code == 400


class TestRestoreRecipeBook:
    """Tests for POST /v1/recipe-books/{id}/restore."""

    def test_restore_recipe_book_success(self, client, mock_db, mock_user):
        """Test restoring an archived recipe book."""
        from datetime import UTC, datetime

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id, archived_at=datetime.now(UTC))
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBook, book, id=book_id, include_archived=True)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/recipe-books/{book_id}/restore")
        assert response.status_code == 200
        assert book.archived_at is None

    def test_restore_recipe_book_not_owner(self, client, mock_db, mock_user):
        """Test that non-owner cannot restore."""
        from datetime import UTC, datetime

        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id, archived_at=datetime.now(UTC))
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBook, book, id=book_id, include_archived=True)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/recipe-books/{book_id}/restore")
        assert response.status_code == 403

    def test_restore_recipe_book_not_found(self, client, mock_db, mock_user):
        """Test restoring nonexistent book."""
        response = client.post("/v1/recipe-books/nonexistent/restore")
        assert response.status_code == 404

    def test_restore_recipe_book_not_archived(self, client, mock_db, mock_user):
        """Test restoring a book that isn't archived."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)  # archived_at is None

        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(RecipeBook, book, id=book_id, include_archived=True)

        response = client.post(f"/v1/recipe-books/{book_id}/restore")
        assert response.status_code == 400


class TestListArchivedRecipeBooks:
    """Tests for GET /v1/recipe-books/archived."""

    def test_list_archived_empty(self, client, mock_db, mock_user):
        """Test listing archived books when none exist."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/recipe-books/archived")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_archived_with_results(self, client, mock_db, mock_user):
        """Test listing archived books with results."""
        from datetime import UTC, datetime

        book = MockRecipeBook(
            id="archived-book",
            name="Old Book",
            archived_at=datetime.now(UTC),
        )
        mock_db.db.query.return_value = MockQuery([(book, 3)])

        response = client.get("/v1/recipe-books/archived")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Old Book"
        assert data["items"][0]["recipe_count"] == 3
        assert data["total"] == 1
