"""Tests for recipe endpoints."""

from conftest import (
    MockIngredient,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
    MockRecipeIngredient,
    MockRecipeStep,
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
