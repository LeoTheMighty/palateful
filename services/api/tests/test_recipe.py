"""Tests for recipe endpoints."""

import uuid
from unittest.mock import patch

from conftest import (
    MockIngredient,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
    MockRecipeIngredient,
    MockRecipeNote,
    MockRecipeStep,
    MockRecipeVersion,
    MockUserFavorite,
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
        # First call returns recipes, second call returns empty favorites
        mock_db.db.query.side_effect = [MockQuery([recipe]), MockQuery([])]

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

    def test_get_recipe_returns_lineage_fields_for_forked_recipe(self, client, mock_db, mock_user):
        """Test that forked recipe returns lineage fields in response."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        src_recipe_id = "original-recipe-id"
        src_book_id = "source-book-id"
        recipe = MockRecipe(
            id=recipe_id,
            recipe_book_id=book_id,
            forked_from_recipe_id=src_recipe_id,
            forked_from_book_id=src_book_id,
            forked_from_recipe_name="Nonna's Pasta",
            forked_from_book_name="Family Recipes",
        )
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
        assert data["forked_from_recipe_name"] == "Nonna's Pasta"
        assert data["forked_from_book_name"] == "Family Recipes"
        assert data["forked_from_recipe_id"] == src_recipe_id
        assert data["forked_from_book_id"] == src_book_id

    def test_get_recipe_lineage_fields_null_for_non_forked(self, client, mock_db, mock_user):
        """Test that non-forked recipe returns null lineage fields."""
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
        assert data["forked_from_recipe_id"] is None
        assert data["forked_from_book_id"] is None
        assert data["forked_from_recipe_name"] is None
        assert data["forked_from_book_name"] is None


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
    """Tests for DELETE /v1/recipes/{recipe_id} (soft delete / archive)."""

    def test_delete_recipe_archives(self, client, mock_db, mock_user):
        """Test deleting a recipe sets archived_at (soft delete)."""
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

        assert recipe.archived_at is None
        response = client.delete(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify soft delete: archived_at should be set
        assert recipe.archived_at is not None

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


class TestRestoreRecipe:
    """Tests for POST /v1/recipes/{recipe_id}/restore."""

    def test_restore_recipe_success(self, client, mock_db, mock_user):
        """Test restoring an archived recipe."""
        from datetime import datetime, UTC

        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(
            id=recipe_id,
            recipe_book_id=book_id,
            archived_at=datetime.now(UTC),
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id, include_archived=True)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/recipes/{recipe_id}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == recipe_id
        # Verify restored
        assert recipe.archived_at is None

    def test_restore_recipe_not_found(self, client, mock_db, mock_user):
        """Test restoring a nonexistent recipe."""
        response = client.post("/v1/recipes/nonexistent/restore")
        assert response.status_code == 404

    def test_restore_recipe_not_archived(self, client, mock_db, mock_user):
        """Test restoring a recipe that is not archived."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id, include_archived=True)

        response = client.post(f"/v1/recipes/{recipe_id}/restore")
        assert response.status_code == 400

    def test_restore_recipe_no_permission(self, client, mock_db, mock_user):
        """Test restoring without owner/editor role fails."""
        from datetime import datetime, UTC

        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(
            id=recipe_id,
            recipe_book_id=book_id,
            archived_at=datetime.now(UTC),
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id, include_archived=True)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(f"/v1/recipes/{recipe_id}/restore")
        assert response.status_code == 403


class TestListArchivedRecipes:
    """Tests for GET /v1/recipes/archived."""

    def test_list_archived_empty(self, client, mock_db, mock_user):
        """Test listing archived recipes when none exist."""
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_where(RecipeBookUser, [])

        response = client.get("/v1/recipes/archived")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_archived_with_results(self, client, mock_db, mock_user):
        """Test listing archived recipes returns archived recipe data."""
        from datetime import datetime, UTC
        from utils.models.recipe_book_user import RecipeBookUser

        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        mock_db.set_where(RecipeBookUser, [membership])

        archived_recipe = MockRecipe(
            name="Old Recipe",
            recipe_book_id=book_id,
            archived_at=datetime.now(UTC),
        )
        mock_db.db.query.return_value = MockQuery([archived_recipe])

        response = client.get("/v1/recipes/archived")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Old Recipe"
        assert data["items"][0]["archived_at"] is not None

    def test_list_archived_requires_auth(self, unauthed_client, mock_db):
        """Test that archived endpoint requires authentication."""
        response = unauthed_client.get("/v1/recipes/archived")
        assert response.status_code in (401, 403, 422)


class TestCreateRecipeWithStepsAndTags:
    """Tests for creating recipes with steps and tags."""

    def test_create_recipe_with_steps(self, client, mock_db, mock_user):
        """Test creating a recipe with structured steps."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={
                "name": "Pasta Carbonara",
                "steps": [
                    {"step_number": 1, "instruction": "Boil water and cook pasta"},
                    {"step_number": 2, "instruction": "Fry guanciale until crispy"},
                    {"step_number": 3, "instruction": "Mix eggs and cheese"},
                ],
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["steps"]) == 3
        assert data["steps"][0]["instruction"] == "Boil water and cook pasta"
        assert data["steps"][0]["step_number"] == 1
        assert data["steps"][2]["step_number"] == 3

    def test_create_recipe_with_tags(self, client, mock_db, mock_user):
        """Test creating a recipe with tags."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={
                "name": "Quick Pasta",
                "tags": ["italian", "quick", "weeknight"],
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tags"] == ["italian", "quick", "weeknight"]

    def test_create_recipe_without_steps_tags(self, client, mock_db, mock_user):
        """Test backward compat: create recipe without steps or tags."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={"name": "Simple Recipe"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tags"] == []
        assert data["steps"] == []

    def test_create_recipe_step_ordering(self, client, mock_db, mock_user):
        """Test that steps preserve step_number ordering."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={
                "name": "Ordered Steps",
                "steps": [
                    {"instruction": "First step"},
                    {"instruction": "Second step"},
                    {"instruction": "Third step"},
                ],
            }
        )
        assert response.status_code == 201
        data = response.json()
        # step_number auto-assigned from index+1 when not provided
        assert data["steps"][0]["step_number"] == 1
        assert data["steps"][1]["step_number"] == 2
        assert data["steps"][2]["step_number"] == 3


class TestUpdateRecipeStepsAndTags:
    """Tests for updating recipe steps and tags."""

    def _setup_update(self, mock_db, mock_user, recipe_id="test-recipe-id",
                      book_id="test-book-id", tags=None):
        """Helper to set up common update test fixtures."""
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, tags=tags or [])
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
        mock_db.db.query.return_value = MockQuery([])
        return recipe

    def test_update_recipe_tags(self, client, mock_db, mock_user):
        """Test updating recipe tags replaces them."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"tags": ["dinner", "healthy"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == ["dinner", "healthy"]

    def test_update_recipe_steps(self, client, mock_db, mock_user):
        """Test updating recipe steps replaces them."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        from utils.models.recipe_step import RecipeStep

        # Simulate the steps that would be returned after delete+recreate
        step1 = MockRecipeStep(recipe_id=recipe_id, step_number=1, instruction="New step 1")
        step2 = MockRecipeStep(recipe_id=recipe_id, step_number=2, instruction="New step 2")
        mock_db.set_where(RecipeStep, [step1, step2])

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={
                "steps": [
                    {"step_number": 1, "instruction": "New step 1"},
                    {"step_number": 2, "instruction": "New step 2"},
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["steps"]) == 2
        assert data["steps"][0]["instruction"] == "New step 1"
        assert data["steps"][1]["instruction"] == "New step 2"

    def test_update_recipe_without_steps_tags(self, client, mock_db, mock_user):
        """Test updating recipe name only doesn't affect steps/tags."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id,
                          tags=["existing"])

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"name": "Updated Name"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        # tags should still be the existing ones
        assert data["tags"] == ["existing"]

    def test_get_recipe_returns_tags(self, client, mock_db, mock_user):
        """Test that get recipe includes tags in response."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(
            id=recipe_id,
            recipe_book_id=book_id,
            tags=["italian", "pasta"]
        )
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
        assert data["tags"] == ["italian", "pasta"]

    def test_get_recipe_returns_steps(self, client, mock_db, mock_user):
        """Test that get recipe includes steps in order."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        step1 = MockRecipeStep(
            recipe_id=recipe_id, step_number=1, instruction="Heat oil"
        )
        step2 = MockRecipeStep(
            recipe_id=recipe_id, step_number=2, instruction="Add garlic"
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_step import RecipeStep

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_where(RecipeStep, [step1, step2])
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["steps"]) == 2
        assert data["steps"][0]["step_number"] == 1
        assert data["steps"][0]["instruction"] == "Heat oil"
        assert data["steps"][1]["step_number"] == 2
        assert data["steps"][1]["instruction"] == "Add garlic"

    def test_list_recipes_returns_tags(self, client, mock_db, mock_user):
        """Test that list recipes includes tags."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        recipe = MockRecipe(
            recipe_book_id=book_id,
            name="Tagged Recipe",
            tags=["quick", "easy"]
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.db.query.side_effect = [MockQuery([recipe]), MockQuery([])]

        response = client.get(f"/v1/recipe-books/{book_id}/recipes")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["tags"] == ["quick", "easy"]


class TestGetRecipePhotoUploadUrl:
    """Tests for POST /v1/recipes/{recipe_id}/photo-upload-url."""

    def test_get_photo_upload_url_success(self, client, mock_db, mock_user):
        """Test getting a presigned URL for recipe photo upload."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/photo-upload-url",
            json={"filename": "photo.jpg"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "s3_key" in data
        assert "content_type" in data
        assert "image_url" in data
        assert data["content_type"] == "image/jpeg"

    def test_get_photo_upload_url_s3_key_pattern(self, client, mock_db, mock_user):
        """Test that S3 key follows the expected pattern."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/photo-upload-url",
            json={"filename": "my_photo.png"},
        )
        assert response.status_code == 200
        data = response.json()
        s3_key = data["s3_key"]
        assert s3_key.startswith(f"recipe-photos/{mock_user.id}/{recipe_id}/")
        assert s3_key.endswith(".png")
        assert data["content_type"] == "image/png"

    def test_get_photo_upload_url_requires_auth(self, unauthed_client, mock_db):
        """Test that endpoint requires authentication."""
        response = unauthed_client.post(
            "/v1/recipes/some-id/photo-upload-url",
            json={"filename": "photo.jpg"},
        )
        # FastAPI security dependency returns 422 when Authorization header is missing
        assert response.status_code in (401, 403, 422)

    def test_get_photo_upload_url_recipe_not_found(self, client, mock_db, mock_user):
        """Test 404 when recipe doesn't exist."""
        response = client.post(
            "/v1/recipes/nonexistent/photo-upload-url",
            json={"filename": "photo.jpg"},
        )
        assert response.status_code == 404

    def test_get_photo_upload_url_no_permission(self, client, mock_db, mock_user):
        """Test 403 when user doesn't have edit access."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/photo-upload-url",
            json={"filename": "photo.jpg"},
        )
        assert response.status_code == 403


class TestToggleFavorite:
    """Tests for POST /v1/recipes/{recipe_id}/favorite."""

    def _setup(self, mock_db, mock_user, recipe_id="test-recipe-id",
               book_id="test-book-id", has_favorite=False):
        """Helper to set up common test fixtures."""
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.user_favorite import UserFavorite

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=mock_user.id,
                           recipe_book_id=book_id)

        if has_favorite:
            fav = MockUserFavorite(user_id=str(mock_user.id), recipe_id=recipe_id)
            mock_db.set_find_by(UserFavorite, fav,
                               user_id=mock_user.id,
                               recipe_id=recipe_id)

        return recipe

    def test_toggle_favorite_add(self, client, mock_db, mock_user):
        """Test adding a recipe to favorites."""
        recipe_id = "test-recipe-id"
        self._setup(mock_db, mock_user, recipe_id=recipe_id)

        response = client.post(f"/v1/recipes/{recipe_id}/favorite")
        assert response.status_code == 201
        data = response.json()
        assert data["is_favorite"] is True

    def test_toggle_favorite_remove(self, client, mock_db, mock_user):
        """Test removing a recipe from favorites."""
        recipe_id = "test-recipe-id"
        self._setup(mock_db, mock_user, recipe_id=recipe_id, has_favorite=True)

        response = client.post(f"/v1/recipes/{recipe_id}/favorite")
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is False

    def test_toggle_favorite_recipe_not_found(self, client, mock_db, mock_user):
        """Test toggling favorite on nonexistent recipe."""
        response = client.post("/v1/recipes/nonexistent/favorite")
        assert response.status_code == 404

    def test_toggle_favorite_no_access(self, client, mock_db, mock_user):
        """Test toggling favorite without recipe book access."""
        recipe_id = "test-recipe-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id="other-book")

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        response = client.post(f"/v1/recipes/{recipe_id}/favorite")
        assert response.status_code == 403


class TestListFavorites:
    """Tests for GET /v1/favorites."""

    def test_list_favorites_empty(self, client, mock_db, mock_user):
        """Test listing favorites when user has none."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/favorites")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_favorites_with_results(self, client, mock_db, mock_user):
        """Test listing favorites returns recipe data."""
        recipe = MockRecipe(name="Favorite Pasta", tags=["italian"])
        fav = MockUserFavorite(user_id=str(mock_user.id), recipe_id=str(recipe.id))
        mock_db.db.query.return_value = MockQuery([(fav, recipe)])

        response = client.get("/v1/favorites")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Favorite Pasta"
        assert data["items"][0]["is_favorite"] is True

    def test_list_favorites_requires_auth(self, unauthed_client, mock_db):
        """Test that favorites endpoint requires authentication."""
        response = unauthed_client.get("/v1/favorites")
        # FastAPI security dependency returns 422 when Authorization header is missing
        assert response.status_code in (401, 403, 422)


class TestGetRecipeFavoriteField:
    """Tests for is_favorite field in GET /v1/recipes/{recipe_id}."""

    def test_get_recipe_shows_favorited(self, client, mock_db, mock_user):
        """Test that get recipe shows is_favorite=true when favorited."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        fav = MockUserFavorite(user_id=str(mock_user.id), recipe_id=recipe_id)

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.user_favorite import UserFavorite

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(UserFavorite, fav,
                           user_id=mock_user.id,
                           recipe_id=recipe_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is True

    def test_get_recipe_shows_not_favorited(self, client, mock_db, mock_user):
        """Test that get recipe shows is_favorite=false when not favorited."""
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
        assert data["is_favorite"] is False


class TestMoveRecipe:
    """Tests for POST /v1/recipes/{recipe_id}/move."""

    def test_move_recipe_success(self, client, mock_db, mock_user):
        """Test moving a recipe to another book."""
        recipe_id = "test-recipe-id"
        src_book_id = "src-book-id"
        dest_book_id = "dest-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=src_book_id)
        dest_book = MockRecipeBook(id=dest_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="owner",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/move",
            json={"destination_book_id": dest_book_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == recipe_id
        assert data["recipe_book_id"] == dest_book_id
        assert recipe.recipe_book_id == dest_book_id

    def test_move_recipe_not_found(self, client, mock_db, mock_user):
        """Test moving a nonexistent recipe."""
        response = client.post(
            "/v1/recipes/nonexistent/move",
            json={"destination_book_id": "some-book"},
        )
        assert response.status_code == 404

    def test_move_recipe_same_book(self, client, mock_db, mock_user):
        """Test moving recipe to same book fails."""
        recipe_id = "test-recipe-id"
        book_id = "same-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/move",
            json={"destination_book_id": book_id},
        )
        assert response.status_code == 400

    def test_move_recipe_no_source_permission(self, client, mock_db, mock_user):
        """Test moving recipe without source book edit permission."""
        recipe_id = "test-recipe-id"
        src_book_id = "src-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=src_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/move",
            json={"destination_book_id": "dest-book-id"},
        )
        assert response.status_code == 403

    def test_move_recipe_no_dest_permission(self, client, mock_db, mock_user):
        """Test moving recipe without destination book edit permission."""
        recipe_id = "test-recipe-id"
        src_book_id = "src-book-id"
        dest_book_id = "dest-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=src_book_id)
        dest_book = MockRecipeBook(id=dest_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="owner",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/move",
            json={"destination_book_id": dest_book_id},
        )
        assert response.status_code == 403

    def test_move_recipe_dest_not_found(self, client, mock_db, mock_user):
        """Test moving recipe to nonexistent destination book."""
        recipe_id = "test-recipe-id"
        src_book_id = "src-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=src_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/move",
            json={"destination_book_id": "nonexistent-book"},
        )
        assert response.status_code == 404


class TestCopyRecipe:
    """Tests for POST /v1/recipes/{recipe_id}/copy."""

    def test_copy_recipe_success(self, client, mock_db, mock_user):
        """Test copying a recipe to another book."""
        recipe_id = "test-recipe-id"
        src_book_id = "src-book-id"
        dest_book_id = "dest-book-id"
        recipe = MockRecipe(
            id=recipe_id,
            recipe_book_id=src_book_id,
            name="Pasta",
            tags=["italian"],
        )
        dest_book = MockRecipeBook(id=dest_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="viewer",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_step import RecipeStep

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)
        mock_db.set_where(RecipeIngredient, [
            MockRecipeIngredient(recipe_id=recipe_id, order_index=0),
        ])
        mock_db.set_where(RecipeStep, [
            MockRecipeStep(recipe_id=recipe_id, step_number=1, instruction="Boil"),
        ])

        response = client.post(
            f"/v1/recipes/{recipe_id}/copy",
            json={"destination_book_id": dest_book_id},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # New recipe should have a different ID
        assert data["id"] != recipe_id

    def test_copy_recipe_not_found(self, client, mock_db, mock_user):
        """Test copying a nonexistent recipe."""
        response = client.post(
            "/v1/recipes/nonexistent/copy",
            json={"destination_book_id": "some-book"},
        )
        assert response.status_code == 404

    def test_copy_recipe_no_source_access(self, client, mock_db, mock_user):
        """Test copying recipe without source book access."""
        recipe_id = "test-recipe-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id="other-book")

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/copy",
            json={"destination_book_id": "dest-book"},
        )
        assert response.status_code == 403

    def test_copy_recipe_no_dest_permission(self, client, mock_db, mock_user):
        """Test copying recipe without destination book edit permission."""
        recipe_id = "test-recipe-id"
        src_book_id = "src-book-id"
        dest_book_id = "dest-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=src_book_id)
        dest_book = MockRecipeBook(id=dest_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="viewer",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/copy",
            json={"destination_book_id": dest_book_id},
        )
        assert response.status_code == 403

    def test_copy_recipe_dest_not_found(self, client, mock_db, mock_user):
        """Test copying recipe to nonexistent destination book."""
        recipe_id = "test-recipe-id"
        src_book_id = "src-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=src_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)

        response = client.post(
            f"/v1/recipes/{recipe_id}/copy",
            json={"destination_book_id": "nonexistent-book"},
        )
        assert response.status_code == 404


class TestBulkMoveRecipes:
    """Tests for POST /v1/recipes/bulk/move."""

    def test_bulk_move_success(self, client, mock_db, mock_user):
        """Test bulk moving recipes to another book."""
        src_book_id = "src-book-id"
        dest_book_id = "dest-book-id"
        recipe1 = MockRecipe(id="recipe-1", recipe_book_id=src_book_id)
        recipe2 = MockRecipe(id="recipe-2", recipe_book_id=src_book_id)
        dest_book = MockRecipeBook(id=dest_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="owner",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe1, id="recipe-1")
        mock_db.set_find_by(Recipe, recipe2, id="recipe-2")
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)

        response = client.post(
            "/v1/recipes/bulk/move",
            json={"recipe_ids": ["recipe-1", "recipe-2"], "destination_book_id": dest_book_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["moved_count"] == 2
        assert recipe1.recipe_book_id == dest_book_id
        assert recipe2.recipe_book_id == dest_book_id

    def test_bulk_move_empty_list(self, client, mock_db, mock_user):
        """Test bulk move with empty recipe list."""
        response = client.post(
            "/v1/recipes/bulk/move",
            json={"recipe_ids": [], "destination_book_id": "some-book"},
        )
        assert response.status_code == 400

    def test_bulk_move_no_dest_permission(self, client, mock_db, mock_user):
        """Test bulk move without destination book permission."""
        dest_book_id = "dest-book-id"
        dest_book = MockRecipeBook(id=dest_book_id)
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="viewer",
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)

        response = client.post(
            "/v1/recipes/bulk/move",
            json={"recipe_ids": ["recipe-1"], "destination_book_id": dest_book_id},
        )
        assert response.status_code == 403

    def test_bulk_move_dest_not_found(self, client, mock_db, mock_user):
        """Test bulk move to nonexistent destination."""
        response = client.post(
            "/v1/recipes/bulk/move",
            json={"recipe_ids": ["recipe-1"], "destination_book_id": "nonexistent"},
        )
        assert response.status_code == 404

    def test_bulk_move_no_source_permission(self, client, mock_db, mock_user):
        """Test bulk move without source book permission."""
        src_book_id = "src-book-id"
        dest_book_id = "dest-book-id"
        recipe = MockRecipe(id="recipe-1", recipe_book_id=src_book_id)
        dest_book = MockRecipeBook(id=dest_book_id)
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="viewer",
        )
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)

        response = client.post(
            "/v1/recipes/bulk/move",
            json={"recipe_ids": ["recipe-1"], "destination_book_id": dest_book_id},
        )
        assert response.status_code == 403

    def test_bulk_move_skips_already_in_dest(self, client, mock_db, mock_user):
        """Test that recipes already in the destination book are skipped."""
        dest_book_id = "dest-book-id"
        src_book_id = "src-book-id"
        recipe_already_there = MockRecipe(id="recipe-1", recipe_book_id=dest_book_id)
        recipe_to_move = MockRecipe(id="recipe-2", recipe_book_id=src_book_id)
        dest_book = MockRecipeBook(id=dest_book_id)
        dest_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=dest_book_id,
            role="owner",
        )
        src_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=src_book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe_already_there, id="recipe-1")
        mock_db.set_find_by(Recipe, recipe_to_move, id="recipe-2")
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, src_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=src_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=dest_book_id)

        response = client.post(
            "/v1/recipes/bulk/move",
            json={"recipe_ids": ["recipe-1", "recipe-2"], "destination_book_id": dest_book_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["moved_count"] == 1  # Only recipe-2 was moved
        assert recipe_to_move.recipe_book_id == dest_book_id


class TestBulkArchiveRecipes:
    """Tests for POST /v1/recipes/bulk/archive."""

    def test_bulk_archive_success(self, client, mock_db, mock_user):
        """Test bulk archiving recipes."""
        book_id = "test-book-id"
        recipe1 = MockRecipe(id="recipe-1", recipe_book_id=book_id)
        recipe2 = MockRecipe(id="recipe-2", recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe1, id="recipe-1")
        mock_db.set_find_by(Recipe, recipe2, id="recipe-2")
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            "/v1/recipes/bulk/archive",
            json={"recipe_ids": ["recipe-1", "recipe-2"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["archived_count"] == 2
        assert recipe1.archived_at is not None
        assert recipe2.archived_at is not None

    def test_bulk_archive_empty_list(self, client, mock_db, mock_user):
        """Test bulk archive with empty recipe list."""
        response = client.post(
            "/v1/recipes/bulk/archive",
            json={"recipe_ids": []},
        )
        assert response.status_code == 400

    def test_bulk_archive_no_permission(self, client, mock_db, mock_user):
        """Test bulk archive without permission."""
        book_id = "test-book-id"
        recipe = MockRecipe(id="recipe-1", recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            "/v1/recipes/bulk/archive",
            json={"recipe_ids": ["recipe-1"]},
        )
        assert response.status_code == 403

    def test_bulk_archive_recipe_not_found(self, client, mock_db, mock_user):
        """Test bulk archive with nonexistent recipe."""
        response = client.post(
            "/v1/recipes/bulk/archive",
            json={"recipe_ids": ["nonexistent"]},
        )
        assert response.status_code == 404


class TestBulkUpdateTags:
    """Tests for POST /v1/recipes/bulk/tags."""

    def test_bulk_add_tags(self, client, mock_db, mock_user):
        """Test bulk adding tags to recipes."""
        book_id = "test-book-id"
        recipe1 = MockRecipe(id="recipe-1", recipe_book_id=book_id, tags=["italian"])
        recipe2 = MockRecipe(id="recipe-2", recipe_book_id=book_id, tags=[])
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe1, id="recipe-1")
        mock_db.set_find_by(Recipe, recipe2, id="recipe-2")
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": ["recipe-1", "recipe-2"], "add_tags": ["quick", "easy"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 2
        assert "quick" in recipe1.tags
        assert "easy" in recipe1.tags
        assert "italian" in recipe1.tags  # preserved
        assert "quick" in recipe2.tags

    def test_bulk_remove_tags(self, client, mock_db, mock_user):
        """Test bulk removing tags from recipes."""
        book_id = "test-book-id"
        recipe = MockRecipe(id="recipe-1", recipe_book_id=book_id, tags=["italian", "quick", "easy"])
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": ["recipe-1"], "remove_tags": ["quick", "easy"]},
        )
        assert response.status_code == 200
        assert recipe.tags == ["italian"]

    def test_bulk_add_and_remove_tags(self, client, mock_db, mock_user):
        """Test bulk adding and removing tags simultaneously."""
        book_id = "test-book-id"
        recipe = MockRecipe(id="recipe-1", recipe_book_id=book_id, tags=["old-tag"])
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": ["recipe-1"], "add_tags": ["new-tag"], "remove_tags": ["old-tag"]},
        )
        assert response.status_code == 200
        assert "new-tag" in recipe.tags
        assert "old-tag" not in recipe.tags

    def test_bulk_tags_empty_list(self, client, mock_db, mock_user):
        """Test bulk tags with empty recipe list."""
        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": [], "add_tags": ["tag"]},
        )
        assert response.status_code == 400

    def test_bulk_tags_no_changes(self, client, mock_db, mock_user):
        """Test bulk tags with no tag changes specified."""
        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": ["recipe-1"]},
        )
        assert response.status_code == 400

    def test_bulk_tags_no_permission(self, client, mock_db, mock_user):
        """Test bulk tags without permission."""
        book_id = "test-book-id"
        recipe = MockRecipe(id="recipe-1", recipe_book_id=book_id, tags=[])
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)

        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": ["recipe-1"], "add_tags": ["tag"]},
        )
        assert response.status_code == 403


class TestGetRecipeVersion:
    """Tests for GET /v1/recipes/{recipe_id}/versions/{version_id}."""

    def test_get_recipe_version_success(self, client, mock_db, mock_user):
        """Test getting a specific recipe version snapshot."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        version_id = "test-version-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        version = MockRecipeVersion(
            id=version_id,
            recipe_id=recipe_id,
            version_number=1,
            snapshot={"name": "Old Name", "ingredients": [], "steps": []},
            changed_fields=["name"],
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeVersion, version, id=version_id)

        response = client.get(f"/v1/recipes/{recipe_id}/versions/{version_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == version_id
        assert data["version_number"] == 1
        assert "snapshot" in data
        assert data["snapshot"]["name"] == "Old Name"
        assert data["changed_fields"] == ["name"]

    def test_get_recipe_version_recipe_not_found(self, client, mock_db, mock_user):
        """Test getting a version for a non-existent recipe."""
        response = client.get("/v1/recipes/nonexistent/versions/some-version")
        assert response.status_code == 404

    def test_get_recipe_version_access_denied(self, client, mock_db, mock_user):
        """Test getting a version without recipe book access."""
        recipe_id = "test-recipe-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id="other-book")

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)

        response = client.get(f"/v1/recipes/{recipe_id}/versions/some-version")
        assert response.status_code == 403

    def test_get_recipe_version_not_found(self, client, mock_db, mock_user):
        """Test getting a version that doesn't exist."""
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
        # RecipeVersion not set — find_by returns None

        response = client.get(f"/v1/recipes/{recipe_id}/versions/nonexistent-version")
        assert response.status_code == 404


class TestRestoreRecipeVersion:
    """Tests for POST /v1/recipes/{recipe_id}/versions/{version_id}/restore."""

    def test_restore_recipe_version_success(self, client, mock_db, mock_user):
        """Test restoring a recipe to a previous version."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        version_id = "test-version-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Current Name")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )
        version = MockRecipeVersion(
            id=version_id,
            recipe_id=recipe_id,
            version_number=1,
            snapshot={
                "name": "Old Name",
                "instructions": "Old instructions",
                "ingredients": [],
                "steps": [],
            },
            changed_fields=["name"],
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeVersion, version, id=version_id)

        response = client.post(f"/v1/recipes/{recipe_id}/versions/{version_id}/restore")
        assert response.status_code == 200
        data = response.json()
        # Recipe name should be updated to snapshot value
        assert data["name"] == "Old Name"
        # A new version snapshot should have been added (db.add called)
        mock_db.db.add.assert_called()
        # The new snapshot version must have changed_fields = ["restore:1"] (AC #3)
        call_args = mock_db.db.add.call_args_list
        added_versions = [a.args[0] for a in call_args if hasattr(a.args[0], 'changed_fields')]
        assert any(v.changed_fields == ["restore:1"] for v in added_versions)

    def test_restore_recipe_version_access_denied(self, client, mock_db, mock_user):
        """Test that viewers cannot restore a recipe version."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)

        response = client.post(f"/v1/recipes/{recipe_id}/versions/some-version/restore")
        assert response.status_code == 403

    def test_restore_recipe_version_recipe_not_found(self, client, mock_db, mock_user):
        """Test restoring a version for a non-existent recipe."""
        response = client.post("/v1/recipes/nonexistent/versions/some-version/restore")
        assert response.status_code == 404

    def test_restore_recipe_version_not_found(self, client, mock_db, mock_user):
        """Test restoring a version that doesn't exist."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        # RecipeVersion not set — find_by returns None

        response = client.post(f"/v1/recipes/{recipe_id}/versions/nonexistent/restore")
        assert response.status_code == 404


class TestAddRecipeNote:
    """Tests for POST /v1/recipes/{recipe_id}/notes."""

    def test_add_recipe_note_success(self, client, mock_db, mock_user):
        """Test adding a note to a recipe returns 201 with note body."""
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

        response = client.post(
            f"/v1/recipes/{recipe_id}/notes",
            json={"body": "great with extra garlic"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["body"] == "great with extra garlic"
        assert "id" in data
        assert "created_at" in data

    def test_add_recipe_note_access_denied(self, client, mock_db, mock_user):
        """Test adding a note to a recipe without access returns 404."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        # No membership set → find_by returns None → 404

        response = client.post(
            f"/v1/recipes/{recipe_id}/notes",
            json={"body": "should fail"},
        )
        assert response.status_code == 404


class TestDeleteRecipeNote:
    """Tests for DELETE /v1/recipes/{recipe_id}/notes/{note_id}."""

    def test_delete_recipe_note_success(self, client, mock_db, mock_user):
        """Test deleting own note returns 200."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        note_id = "test-note-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="viewer",
        )
        note = MockRecipeNote(
            id=note_id,
            recipe_id=recipe_id,
            created_by=str(mock_user.id),
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeNote, note, id=note_id)

        response = client.delete(f"/v1/recipes/{recipe_id}/notes/{note_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    def test_delete_recipe_note_not_found(self, client, mock_db, mock_user):
        """Test deleting a non-existent note returns 404."""
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
        # RecipeNote not set → find_by returns None → 404

        response = client.delete(f"/v1/recipes/{recipe_id}/notes/nonexistent")
        assert response.status_code == 404

    def test_delete_recipe_note_unauthorized(self, client, mock_db, mock_user):
        """Test deleting another user's note as editor returns 403."""
        import uuid
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        note_id = "test-note-id"
        other_user_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="editor",  # editor, not owner
        )
        note = MockRecipeNote(
            id=note_id,
            recipe_id=recipe_id,
            created_by=other_user_id,  # someone else's note
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeNote, note, id=note_id)

        response = client.delete(f"/v1/recipes/{recipe_id}/notes/{note_id}")
        assert response.status_code == 403


class TestCreateRecipeMissingBranches:
    """Tests for missing branches in create_recipe.py."""

    def test_create_recipe_book_not_found(self, client, mock_db, mock_user):
        """Test creating recipe when book exists in membership but not in find_by (line 51)."""
        book_id = "test-book-id"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        # RecipeBook not set -> find_by returns None -> 404

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={"name": "New Recipe"}
        )
        assert response.status_code == 404

    def test_create_recipe_with_ingredients(self, client, mock_db, mock_user):
        """Test creating recipe with ingredients including normalization (lines 84-119)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        ingredient_id = str(uuid.uuid4())
        ingredient = MockIngredient(id=ingredient_id, canonical_name="flour", category="baking")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.ingredient import Ingredient

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_find_by(Ingredient, ingredient, id=ingredient_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={
                "name": "Recipe With Ingredients",
                "ingredients": [
                    {
                        "ingredient_id": ingredient_id,
                        "quantity": 2.0,
                        "unit": "cups",
                    }
                ],
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["ingredients"]) == 1
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "flour"

    def test_create_recipe_ingredient_not_found(self, client, mock_db, mock_user):
        """Test creating recipe with nonexistent ingredient (line 85-90)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        # Ingredient not configured -> find_by returns None -> 400

        response = client.post(
            f"/v1/recipe-books/{book_id}/recipes",
            json={
                "name": "Bad Ingredient Recipe",
                "ingredients": [
                    {
                        "ingredient_id": "nonexistent-ingredient",
                        "quantity": 1.0,
                        "unit": "cups",
                    }
                ],
            }
        )
        assert response.status_code == 400

    def test_create_recipe_normalization_failure(self, client, mock_db, mock_user):
        """Test creating recipe when quantity normalization fails (lines 100-103)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        ingredient_id = str(uuid.uuid4())
        ingredient = MockIngredient(id=ingredient_id, canonical_name="spice")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.ingredient import Ingredient

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_find_by(Ingredient, ingredient, id=ingredient_id)

        # Patch normalize_quantity to raise an exception
        with patch("api.v1.recipe.create_recipe.normalize_quantity", side_effect=Exception("unsupported unit")):
            response = client.post(
                f"/v1/recipe-books/{book_id}/recipes",
                json={
                    "name": "Fallback Normalization Recipe",
                    "ingredients": [
                        {
                            "ingredient_id": ingredient_id,
                            "quantity": 3.0,
                            "unit": "pinches",
                        }
                    ],
                }
            )
        assert response.status_code == 201
        data = response.json()
        assert len(data["ingredients"]) == 1

    def test_create_recipe_embedding_none(self, client, mock_db, mock_user):
        """Test creating recipe when embedding generation returns None (line 76->81 false branch)."""
        book_id = "test-book-id"
        book = MockRecipeBook(id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                           user_id=str(mock_user.id),
                           recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=None):
            response = client.post(
                f"/v1/recipe-books/{book_id}/recipes",
                json={"name": "No Embedding Recipe"}
            )
        assert response.status_code == 201


class TestUpdateRecipeMissingBranches:
    """Tests for missing branches in update_recipe.py."""

    def _setup_update(self, mock_db, mock_user, recipe_id="test-recipe-id",
                      book_id="test-book-id", tags=None, name="Test Recipe"):
        """Helper to set up common update test fixtures."""
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, tags=tags or [], name=name)
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
        mock_db.db.query.return_value = MockQuery([])
        return recipe

    def test_update_recipe_description(self, client, mock_db, mock_user):
        """Test updating description field."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"description": "Updated description"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    def test_update_recipe_servings(self, client, mock_db, mock_user):
        """Test updating servings field."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"servings": 8}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["servings"] == 8

    def test_update_recipe_prep_time(self, client, mock_db, mock_user):
        """Test updating prep_time field."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"prep_time": 45}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prep_time"] == 45

    def test_update_recipe_cook_time(self, client, mock_db, mock_user):
        """Test updating cook_time field."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"cook_time": 60}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cook_time"] == 60

    def test_update_recipe_image_url(self, client, mock_db, mock_user):
        """Test updating image_url field."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"image_url": "https://example.com/photo.jpg"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["image_url"] == "https://example.com/photo.jpg"

    def test_update_recipe_source_url(self, client, mock_db, mock_user):
        """Test updating source_url field."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"source_url": "https://example.com/recipe"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_url"] == "https://example.com/recipe"

    def test_update_recipe_with_ingredients(self, client, mock_db, mock_user):
        """Test updating recipe ingredients (delete-and-recreate)."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        ingredient_id = str(uuid.uuid4())
        ingredient = MockIngredient(id=ingredient_id, canonical_name="sugar")
        recipe = self._setup_update(mock_db, mock_user, recipe_id=recipe_id, book_id=book_id)

        from utils.models.ingredient import Ingredient
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_step import RecipeStep
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Ingredient, ingredient, id=ingredient_id)
        mock_db.set_where(RecipeIngredient, [])
        mock_db.set_where(RecipeStep, [])
        mock_db.set_where(RecipeNote, [])

        # db.query calls in order:
        # 1. func.max(RecipeVersion.version_number) during _create_version_snapshot
        # 2. RecipeIngredient join Ingredient for response
        ri = MockRecipeIngredient(recipe_id=recipe_id, ingredient_id=ingredient_id)
        mock_db.db.query.side_effect = [
            MockQuery([0]),                  # max version_number
            MockQuery([(ri, ingredient)]),   # ingredient join for response
        ]

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={
                "ingredients": [
                    {
                        "ingredient_id": ingredient_id,
                        "quantity": 1.5,
                        "unit": "cups",
                    }
                ],
            }
        )
        assert response.status_code == 200

    def test_update_recipe_ingredient_not_found(self, client, mock_db, mock_user):
        """Test updating recipe with nonexistent ingredient returns 400."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_step import RecipeStep
        from utils.models.recipe_note import RecipeNote

        mock_db.set_where(RecipeIngredient, [])
        mock_db.set_where(RecipeStep, [])
        mock_db.set_where(RecipeNote, [])

        # _create_version_snapshot calls db.query for max version_number
        mock_db.db.query.return_value = MockQuery([0])

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={
                "ingredients": [
                    {
                        "ingredient_id": "nonexistent",
                        "quantity": 1.0,
                        "unit": "cups",
                    }
                ],
            }
        )
        assert response.status_code == 400

    def test_update_recipe_normalization_failure(self, client, mock_db, mock_user):
        """Test updating recipe when normalization fails uses display values."""
        recipe_id = "test-recipe-id"
        ingredient_id = str(uuid.uuid4())
        ingredient = MockIngredient(id=ingredient_id, canonical_name="saffron")
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        from utils.models.ingredient import Ingredient
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_step import RecipeStep
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Ingredient, ingredient, id=ingredient_id)
        mock_db.set_where(RecipeIngredient, [])
        mock_db.set_where(RecipeStep, [])
        mock_db.set_where(RecipeNote, [])

        ri = MockRecipeIngredient(recipe_id=recipe_id, ingredient_id=ingredient_id)
        mock_db.db.query.side_effect = [
            MockQuery([0]),                  # max version_number
            MockQuery([(ri, ingredient)]),   # ingredient join for response
        ]

        with patch("api.v1.recipe.update_recipe.normalize_quantity", side_effect=Exception("bad unit")):
            response = client.put(
                f"/v1/recipes/{recipe_id}",
                json={
                    "ingredients": [
                        {
                            "ingredient_id": ingredient_id,
                            "quantity": 0.5,
                            "unit": "pinch",
                        }
                    ],
                }
            )
        assert response.status_code == 200

    def test_update_recipe_same_name_skips_embedding(self, client, mock_db, mock_user):
        """Test that sending the same name value skips embedding regeneration."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id, name="Test Recipe")

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding") as mock_embed:
            response = client.put(
                f"/v1/recipes/{recipe_id}",
                json={"name": "Test Recipe"}  # same as existing
            )
        assert response.status_code == 200
        mock_embed.assert_not_called()  # no embedding regen needed

    def test_update_recipe_embedding_regeneration(self, client, mock_db, mock_user):
        """Test that updating name/description/tags regenerates embedding."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=[0.1, 0.2]) as mock_embed:
            response = client.put(
                f"/v1/recipes/{recipe_id}",
                json={"description": "New searchable description"}
            )
        assert response.status_code == 200
        mock_embed.assert_called_once()

    def test_update_recipe_embedding_returns_none(self, client, mock_db, mock_user):
        """Test that embedding=None branch is handled when updating searchable fields."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=None):
            response = client.put(
                f"/v1/recipes/{recipe_id}",
                json={"description": "Another desc"}
            )
        assert response.status_code == 200

    def test_update_recipe_no_changes(self, client, mock_db, mock_user):
        """Test updating recipe with no fields changed."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={}
        )
        assert response.status_code == 200

    def test_update_recipe_versioning_on_name_change(self, client, mock_db, mock_user):
        """Test that changing name triggers a version snapshot."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id, name="Old Name")

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"name": "New Name"}
        )
        assert response.status_code == 200
        # Verify db.add was called (version snapshot created)
        mock_db.db.add.assert_called()

    def test_update_recipe_versioning_on_instructions_change(self, client, mock_db, mock_user):
        """Test that changing instructions triggers a version snapshot."""
        recipe_id = "test-recipe-id"
        self._setup_update(mock_db, mock_user, recipe_id=recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={"instructions": "New instructions here"}
        )
        assert response.status_code == 200
        mock_db.db.add.assert_called()


class TestGetRecipeVersionsMissingBranches:
    """Tests for missing branches in get_recipe_versions.py."""

    def test_get_recipe_versions_success(self, client, mock_db, mock_user):
        """Test getting version history for a recipe (full success path)."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        version1 = MockRecipeVersion(
            recipe_id=recipe_id,
            version_number=1,
            changed_fields=["name"],
        )
        version2 = MockRecipeVersion(
            recipe_id=recipe_id,
            version_number=2,
            changed_fields=["ingredients"],
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_where(RecipeVersion, [version2, version1])

        response = client.get(f"/v1/recipes/{recipe_id}/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["recipe_id"] == recipe_id
        assert data["total"] == 2
        assert len(data["versions"]) == 2

    def test_get_recipe_versions_recipe_not_found(self, client, mock_db, mock_user):
        """Test getting versions for a nonexistent recipe."""
        response = client.get("/v1/recipes/nonexistent/versions")
        assert response.status_code == 404

    def test_get_recipe_versions_access_denied(self, client, mock_db, mock_user):
        """Test getting versions without membership."""
        recipe_id = "test-recipe-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id="other-book")

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        # No membership -> find_by returns None -> 403

        response = client.get(f"/v1/recipes/{recipe_id}/versions")
        assert response.status_code == 403

    def test_get_recipe_versions_empty(self, client, mock_db, mock_user):
        """Test getting versions when there are no versions."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_where(RecipeVersion, [])

        response = client.get(f"/v1/recipes/{recipe_id}/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["versions"] == []


class TestRestoreRecipeVersionMissingBranches:
    """Tests for missing branches in restore_recipe_version.py."""

    def test_restore_version_with_ingredients_and_steps(self, client, mock_db, mock_user):
        """Test restoring a version with ingredients and steps in snapshot (lines 93-151)."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        version_id = "test-version-id"
        ingredient_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Current Name")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",
        )
        ingredient = MockIngredient(id=ingredient_id, canonical_name="flour")
        version = MockRecipeVersion(
            id=version_id,
            recipe_id=recipe_id,
            version_number=1,
            snapshot={
                "name": "Old Name",
                "instructions": "Old instructions",
                "ingredients": [
                    {
                        "ingredient_id": ingredient_id,
                        "quantity_display": "2",
                        "unit_display": "cups",
                        "notes": None,
                        "is_optional": False,
                        "order_index": 0,
                    }
                ],
                "steps": [
                    {
                        "step_number": 1,
                        "instruction": "Mix ingredients",
                        "active_time_minutes": 5,
                        "timers": None,
                        "wait_time_minutes": None,
                        "wait_type": None,
                        "can_prep_ahead": False,
                        "is_optional": False,
                    }
                ],
            },
            changed_fields=["name", "ingredients", "steps"],
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_version import RecipeVersion
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_step import RecipeStep
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeVersion, version, id=version_id)
        mock_db.set_where(RecipeIngredient, [])
        mock_db.set_where(RecipeStep, [])
        mock_db.set_where(RecipeNote, [])
        mock_db.set_where(RecipeVersion, [])

        # db.query calls in order:
        # 1. func.max(RecipeVersion.version_number) in _create_restore_snapshot
        # 2. RecipeIngredient join Ingredient for response (uses self.db.query)
        ri = MockRecipeIngredient(recipe_id=recipe_id, ingredient_id=ingredient_id)
        mock_db.db.query.side_effect = [
            MockQuery([0]),                  # max version_number
            MockQuery([(ri, ingredient)]),   # ingredient join for response
        ]

        response = client.post(f"/v1/recipes/{recipe_id}/versions/{version_id}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Old Name"


class TestAddRecipeNoteMissingBranches:
    """Tests for missing branches in add_recipe_note.py."""

    def test_add_note_recipe_not_found(self, client, mock_db, mock_user):
        """Test adding note to a nonexistent recipe (line 35-40)."""
        response = client.post(
            "/v1/recipes/nonexistent/notes",
            json={"body": "should fail"},
        )
        assert response.status_code == 404

    def test_add_note_empty_body_rejected(self, client, mock_db, mock_user):
        """Test that empty body is rejected by validator."""
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

        response = client.post(
            f"/v1/recipes/{recipe_id}/notes",
            json={"body": "   "},
        )
        assert response.status_code == 422


class TestDeleteRecipeNoteMissingBranches:
    """Tests for missing branches in delete_recipe_note.py."""

    def test_delete_note_wrong_recipe_id(self, client, mock_db, mock_user):
        """Test deleting a note that belongs to a different recipe (line 47)."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        note_id = "test-note-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        note = MockRecipeNote(
            id=note_id,
            recipe_id="different-recipe-id",  # Different recipe
            created_by=str(mock_user.id),
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeNote, note, id=note_id)

        response = client.delete(f"/v1/recipes/{recipe_id}/notes/{note_id}")
        assert response.status_code == 404

    def test_delete_note_already_archived(self, client, mock_db, mock_user):
        """Test deleting a note that is already archived (line 47)."""
        from datetime import datetime, UTC

        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        note_id = "test-note-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
        )
        note = MockRecipeNote(
            id=note_id,
            recipe_id=recipe_id,
            created_by=str(mock_user.id),
            archived_at=datetime.now(UTC),  # Already archived
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeNote, note, id=note_id)

        response = client.delete(f"/v1/recipes/{recipe_id}/notes/{note_id}")
        assert response.status_code == 404

    def test_delete_note_as_book_owner(self, client, mock_db, mock_user):
        """Test that book owner can delete another user's note (line 56)."""
        other_user_id = str(uuid.uuid4())
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        note_id = "test-note-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=book_id,
            role="owner",  # Owner
        )
        note = MockRecipeNote(
            id=note_id,
            recipe_id=recipe_id,
            created_by=other_user_id,  # Someone else's note
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_note import RecipeNote

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id),
                            recipe_book_id=book_id)
        mock_db.set_find_by(RecipeNote, note, id=note_id)

        response = client.delete(f"/v1/recipes/{recipe_id}/notes/{note_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    def test_delete_note_recipe_no_membership(self, client, mock_db, mock_user):
        """Test deleting note without book membership (line 38-43)."""
        recipe_id = "test-recipe-id"
        book_id = "test-book-id"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id)

        from utils.models.recipe import Recipe

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        # No membership set -> 404

        response = client.delete(f"/v1/recipes/{recipe_id}/notes/some-note")
        assert response.status_code == 404


class TestParseQuantityDisplay:
    """Tests for _parse_quantity_display helper in restore_recipe_version.py (lines 30-42)."""

    def test_parse_integer(self):
        """Test parsing integer string."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display
        from decimal import Decimal

        result = _parse_quantity_display("2")
        assert result == Decimal("2.0")

    def test_parse_decimal(self):
        """Test parsing decimal string."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display
        from decimal import Decimal

        result = _parse_quantity_display("0.5")
        assert result == Decimal("0.5")

    def test_parse_fraction(self):
        """Test parsing fraction string."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display
        from decimal import Decimal

        result = _parse_quantity_display("1/2")
        assert result == Decimal("0.5")

    def test_parse_mixed_number(self):
        """Test parsing mixed number string (line 33-37)."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display
        from decimal import Decimal

        result = _parse_quantity_display("1 1/2")
        assert result == Decimal("1.5")

    def test_parse_mixed_number_with_quarter(self):
        """Test parsing mixed number with quarter fraction."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display
        from decimal import Decimal

        result = _parse_quantity_display("1 1/4")
        assert result == Decimal("1.25")

    def test_parse_invalid_falls_back(self):
        """Test parsing unparsable string falls back to Decimal(s) (line 41-42)."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display
        from decimal import Decimal

        result = _parse_quantity_display("3.5")
        assert result == Decimal("3.5")
