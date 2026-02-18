"""Tests for public (no-auth) recipe and recipe book endpoints."""

from conftest import (
    MockIngredient,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeIngredient,
)


class TestGetPublicRecipe:
    """Tests for GET /v1/recipes/{recipe_id}/public."""

    def test_public_recipe_success(self, client, mock_db):
        """Test getting a public recipe."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        book = MockRecipeBook(id=book_id, is_public=True, name="Public Book")

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/recipes/{recipe_id}/public")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == recipe_id
        assert data["recipe_book_name"] == "Public Book"

    def test_public_recipe_not_public_book(self, client, mock_db):
        """Test that recipe in non-public book returns 404."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        book = MockRecipeBook(id=book_id, is_public=False)

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.get(f"/v1/recipes/{recipe_id}/public")
        assert response.status_code == 404

    def test_public_recipe_not_found(self, client, mock_db):
        """Test getting a public recipe that doesn't exist."""
        response = client.get("/v1/recipes/nonexistent/public")
        assert response.status_code == 404

    def test_public_recipe_with_ingredients(self, client, mock_db):
        """Test getting a public recipe that has ingredients."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        book = MockRecipeBook(id=book_id, is_public=True, name="Public Book")
        ri = MockRecipeIngredient(recipe_id=recipe_id)
        ingredient = MockIngredient(canonical_name="sugar")

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.db.query.return_value = MockQuery([(ri, ingredient)])

        response = client.get(f"/v1/recipes/{recipe_id}/public")
        assert response.status_code == 200
        data = response.json()
        assert len(data["ingredients"]) == 1
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "sugar"


class TestGetPublicRecipeBook:
    """Tests for GET /v1/recipe-books/{book_id}/public."""

    def test_public_recipe_book_success(self, client, mock_db):
        """Test getting a public recipe book."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id, is_public=True, name="Public Book")
        recipe = MockRecipe(recipe_book_id=book_id, name="Public Recipe")

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe import Recipe

        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_where(Recipe, [recipe])

        response = client.get(f"/v1/recipe-books/{book_id}/public")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == book_id
        assert data["name"] == "Public Book"
        assert data["is_public"] is True
        assert data["recipe_count"] == 1
        assert len(data["recipes"]) == 1

    def test_public_recipe_book_not_public(self, client, mock_db):
        """Test that private recipe book returns 404."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id, is_public=False)

        from utils.models.recipe_book import RecipeBook

        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.get(f"/v1/recipe-books/{book_id}/public")
        assert response.status_code == 404

    def test_public_recipe_book_not_found(self, client, mock_db):
        """Test getting a nonexistent public recipe book."""
        response = client.get("/v1/recipe-books/nonexistent/public")
        assert response.status_code == 404

    def test_public_recipe_book_empty(self, client, mock_db):
        """Test getting a public recipe book with no recipes."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id, is_public=True)

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe import Recipe

        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_where(Recipe, [])

        response = client.get(f"/v1/recipe-books/{book_id}/public")
        assert response.status_code == 200
        data = response.json()
        assert data["recipe_count"] == 0
        assert data["recipes"] == []
