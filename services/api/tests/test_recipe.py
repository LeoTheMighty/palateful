"""Tests for recipe endpoints."""

from conftest import (
    MockIngredient,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
    MockRecipeIngredient,
)


class TestListRecipes:
    """Tests for GET /v1/recipe-books/{book_id}/recipes."""

    def test_list_recipes_success(self, client, mock_db, mock_user):
        """Test listing recipes in a book."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        recipe = MockRecipe(recipe_book_id=book_id, name="Pasta")

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.db.query.return_value = MockQuery([recipe])

        response = client.get(f"/v1/recipe-books/{book_id}/recipes")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_recipes_no_access(self, client, mock_db, mock_user):
        """Test listing recipes without access."""
        response = client.get("/v1/recipe-books/no-access/recipes")
        assert response.status_code == 403

    def test_list_recipes_with_search(self, client, mock_db, mock_user):
        """Test listing recipes with search query."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/recipe-books/{book_id}/recipes?search=pasta")
        assert response.status_code == 200


class TestGetRecipe:
    """Tests for GET /v1/recipes/{recipe_id}."""

    def test_get_recipe_success(self, client, mock_db, mock_user):
        """Test getting a recipe."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == recipe_id
        assert data["name"] == recipe.name
        assert "ingredients" in data

    def test_get_recipe_not_found(self, client, mock_db, mock_user):
        """Test getting a recipe that doesn't exist."""
        response = client.get("/v1/recipes/nonexistent")
        assert response.status_code == 404

    def test_get_recipe_no_access(self, client, mock_db, mock_user):
        """Test getting a recipe without access to the book."""
        recipe_id = "test-recipe-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id="other-book")

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        response = client.get(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 403

    def test_get_recipe_with_ingredients(self, client, mock_db, mock_user):
        """Test getting a recipe that has ingredients."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        ri = MockRecipeIngredient(recipe_id=recipe_id)
        ingredient = MockIngredient(canonical_name="flour")

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.db.query.return_value = MockQuery([(ri, ingredient)])

        response = client.get(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["ingredients"]) == 1
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "flour"


class TestCreateRecipe:
    """Tests for POST /v1/recipe-books/{book_id}/recipes."""

    def test_create_recipe_success(self, client, mock_db, mock_user):
        """Test creating a recipe."""
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

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={
                "name": "New Recipe",
                "description": "A new recipe",
                "servings": 4,
                "prep_time": 10,
                "cook_time": 20,
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Recipe"
        assert data["servings"] == 4

    def test_create_recipe_no_permission(self, client, mock_db, mock_user):
        """Test creating a recipe without editor access."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer"
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={"name": "Test"}
        )
        assert response.status_code == 403

    def test_create_recipe_missing_name(self, client, mock_db):
        """Test creating a recipe without name fails."""
        response = client.post(
            "/v1/recipe-books/some-id/recipes",
            json={"description": "No name"}
        )
        assert response.status_code == 422


class TestDeleteRecipe:
    """Tests for DELETE /v1/recipes/{recipe_id}."""

    def test_delete_recipe_success(self, client, mock_db, mock_user):
        """Test deleting a recipe."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_recipe_not_found(self, client, mock_db):
        """Test deleting a recipe that doesn't exist."""
        response = client.delete("/v1/recipes/nonexistent")
        assert response.status_code == 404

    def test_delete_recipe_no_permission(self, client, mock_db, mock_user):
        """Test deleting a recipe as viewer fails."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer"
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.delete(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 403
