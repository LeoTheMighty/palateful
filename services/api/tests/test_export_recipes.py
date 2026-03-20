"""Tests for ExportRecipes endpoint."""

import uuid
from decimal import Decimal

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
)


def _setup_recipe_book(mock_db, mock_user, book_id=None, recipe_id=None):
    """Set up a single book with one recipe for success-path tests."""
    book_id = book_id or str(uuid.uuid4())
    recipe_id = recipe_id or str(uuid.uuid4())
    ingredient_id = str(uuid.uuid4())

    membership = MockRecipeBookUser(
        user_id=str(mock_user.id), recipe_book_id=book_id, role="owner"
    )
    book = MockRecipeBook(id=book_id, name="My Recipes", description="Test book")
    recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Pasta")
    ingredient = MockIngredient(id=ingredient_id, canonical_name="flour")
    ri = MockRecipeIngredient(
        recipe_id=recipe_id,
        ingredient_id=ingredient_id,
        quantity_display=Decimal("2.000"),
        unit_display="cups",
    )
    step = MockRecipeStep(
        recipe_id=recipe_id, step_number=1, instruction="Boil water"
    )
    note = MockRecipeNote(recipe_id=recipe_id, body="Great recipe")
    version = MockRecipeVersion(recipe_id=recipe_id, version_number=1)

    from utils.models.recipe import Recipe
    from utils.models.recipe_book import RecipeBook
    from utils.models.recipe_book_user import RecipeBookUser
    from utils.models.recipe_note import RecipeNote
    from utils.models.recipe_step import RecipeStep
    from utils.models.recipe_version import RecipeVersion

    mock_db.set_where(RecipeBookUser, [membership])
    mock_db.set_find_by(RecipeBook, book, id=book_id)
    mock_db.set_where(Recipe, [recipe])
    mock_db.set_where(RecipeStep, [step])
    mock_db.set_where(RecipeNote, [note])
    mock_db.set_where(RecipeVersion, [version])
    mock_db.db.query.return_value = MockQuery([(ri, ingredient)])

    return book_id, recipe_id


class TestExportRecipesSuccess:
    """Core success path — data is returned correctly."""

    def test_export_returns_correct_counts(self, client, mock_db, mock_user):
        """Returns correct book_count and recipe_count."""
        book_id, _ = _setup_recipe_book(mock_db, mock_user)

        response = client.get("/v1/users/me/export")

        assert response.status_code == 200
        data = response.json()
        assert data["book_count"] == 1
        assert data["recipe_count"] == 1
        assert "exported_at" in data

    def test_export_returns_book_and_recipe_structure(self, client, mock_db, mock_user):
        """Returns correct book/recipe structure with all fields."""
        book_id, recipe_id = _setup_recipe_book(mock_db, mock_user)

        response = client.get("/v1/users/me/export")

        assert response.status_code == 200
        data = response.json()
        book = data["books"][0]
        assert book["id"] == book_id
        assert book["name"] == "My Recipes"
        assert book["role"] == "owner"

        recipe = book["recipes"][0]
        assert recipe["id"] == recipe_id
        assert recipe["name"] == "Pasta"

    def test_export_includes_steps_ingredients_notes_versions(
        self, client, mock_db, mock_user
    ):
        """Recipe data includes all nested collections."""
        _setup_recipe_book(mock_db, mock_user)

        response = client.get("/v1/users/me/export")

        assert response.status_code == 200
        recipe = response.json()["books"][0]["recipes"][0]

        assert len(recipe["steps"]) == 1
        assert recipe["steps"][0]["instruction"] == "Boil water"
        assert recipe["steps"][0]["step_number"] == 1

        assert len(recipe["ingredients"]) == 1
        assert recipe["ingredients"][0]["canonical_name"] == "flour"
        assert recipe["ingredients"][0]["unit_display"] == "cups"

        assert len(recipe["notes"]) == 1
        assert recipe["notes"][0]["body"] == "Great recipe"

        assert len(recipe["versions"]) == 1
        assert recipe["versions"][0]["version_number"] == 1


class TestExportRecipesEmptyCollection:
    """Empty collection paths."""

    def test_export_empty_collection(self, client, mock_db, mock_user):
        """Empty collection returns book_count=0, recipe_count=0, books=[]."""
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_where(RecipeBookUser, [])

        response = client.get("/v1/users/me/export")

        assert response.status_code == 200
        data = response.json()
        assert data["book_count"] == 0
        assert data["recipe_count"] == 0
        assert data["books"] == []

    def test_export_book_with_no_recipes(self, client, mock_db, mock_user):
        """A book with no recipes contributes to book_count but not recipe_count."""
        book_id = str(uuid.uuid4())
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner"
        )
        book = MockRecipeBook(id=book_id, name="Empty Book")

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_where(RecipeBookUser, [membership])
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_where(Recipe, [])

        response = client.get("/v1/users/me/export")

        assert response.status_code == 200
        data = response.json()
        assert data["book_count"] == 1
        assert data["recipe_count"] == 0
        assert data["books"][0]["recipes"] == []


class TestExportRecipesSkipsArchivedBooks:
    """Archived books are excluded from the export."""

    def test_archived_book_is_skipped(self, client, mock_db, mock_user):
        """Membership for an archived (or missing) book is skipped — book_count stays 0."""
        book_id = str(uuid.uuid4())
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner"
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_where(RecipeBookUser, [membership])
        # find_by returns None — simulates archived or deleted book
        mock_db.set_find_by(RecipeBook, None, id=book_id)

        response = client.get("/v1/users/me/export")

        assert response.status_code == 200
        data = response.json()
        assert data["book_count"] == 0
        assert data["recipe_count"] == 0
        assert data["books"] == []


class TestExportRecipesAuth:
    """Authentication tests."""

    def test_export_unauthenticated_rejected(self, unauthed_client):
        """Unauthenticated requests are rejected (missing required auth header)."""
        response = unauthed_client.get("/v1/users/me/export")
        assert response.status_code in (401, 422)
