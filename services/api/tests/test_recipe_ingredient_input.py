"""Tests for bugs-imp-ing-5 — recipe create/update accept name or id.

Verifies that `CreateRecipe.IngredientInput` / `UpdateRecipe.IngredientInput`
round-trip through the shared `utils.services.ingredient_resolver.resolve_ingredient`
helper:
* `ingredient_id` alone → existing canonical lookup path (unchanged).
* `name` alone → find-or-create by lowercased/stripped canonical_name.
* both present → `ingredient_id` wins (no silent name drift).
* neither present → 400 / INGREDIENT_INPUT_REQUIRED.
"""

import uuid

import pytest
from conftest import (
    MockIngredient,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
)
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser


@pytest.fixture
def book_and_membership(mock_db, mock_user):
    """Authenticated owner membership on a recipe book."""
    book_id = "test-book-id"
    book = MockRecipeBook(id=book_id)
    membership = MockRecipeBookUser(
        user_id=str(mock_user.id),
        recipe_book_id=book_id,
        role="owner",
    )
    mock_db.set_find_by(
        RecipeBookUser,
        membership,
        user_id=str(mock_user.id),
        recipe_book_id=book_id,
    )
    mock_db.set_find_by(RecipeBook, book, id=book_id)
    return book_id


class TestCreateRecipeNameOrId:
    def test_name_only_creates_pending_review_ingredient(
        self, client, mock_db, book_and_membership
    ):
        """Name-only input takes the find-or-create path."""
        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Name-Only Recipe",
                "ingredients": [
                    {
                        "name": "Butter",
                        "quantity": 0.5,
                        "unit": "cup",
                        "notes": "melted",
                    }
                ],
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert len(data["ingredients"]) == 1
        # canonical_name lowercased + stripped.
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "butter"

    def test_name_reuses_existing_ingredient(
        self, client, mock_db, book_and_membership
    ):
        """A name that already has a canonical row uses that row — no duplicate."""
        existing_id = str(uuid.uuid4())
        existing = MockIngredient(
            id=existing_id, canonical_name="salt", is_canonical=True
        )
        mock_db.set_find_by(Ingredient, existing, canonical_name="salt")

        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Reuses Ingredient",
                "ingredients": [
                    {"name": "Salt", "quantity": 1, "unit": "tsp"}
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ingredients"][0]["ingredient"]["id"] == existing_id
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "salt"

    def test_blank_name_rejected(self, client, book_and_membership):
        """Whitespace-only name is not a valid handle."""
        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Blank Name Recipe",
                "ingredients": [
                    {"name": "   ", "quantity": 1, "unit": "tsp"}
                ],
            },
        )
        assert response.status_code == 400

    def test_ingredient_id_only_still_works(
        self, client, mock_db, book_and_membership
    ):
        """Backwards compat — existing clients supplying only ingredient_id."""
        ing_id = str(uuid.uuid4())
        existing = MockIngredient(id=ing_id, canonical_name="flour")
        mock_db.set_find_by(Ingredient, existing, id=ing_id)

        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "ID-Only Recipe",
                "ingredients": [
                    {"ingredient_id": ing_id, "quantity": 2, "unit": "cups"}
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ingredients"][0]["ingredient"]["id"] == ing_id

    def test_both_id_and_name_supplied_id_wins(
        self, client, mock_db, book_and_membership
    ):
        """When both inputs arrive, ingredient_id wins (guards against name drift)."""
        ing_id = str(uuid.uuid4())
        existing = MockIngredient(id=ing_id, canonical_name="sugar")
        mock_db.set_find_by(Ingredient, existing, id=ing_id)

        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Both Recipe",
                "ingredients": [
                    {
                        "ingredient_id": ing_id,
                        "name": "totally different typo",
                        "quantity": 1,
                        "unit": "cup",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        # Canonical name comes from the ID-resolved row, not the typo.
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "sugar"

    def test_neither_id_nor_name_is_400(self, client, book_and_membership):
        """Both absent → 400 INGREDIENT_INPUT_REQUIRED."""
        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Missing Input Recipe",
                "ingredients": [
                    {"quantity": 1, "unit": "cup"}
                ],
            },
        )
        assert response.status_code == 400

    def test_ingredient_id_not_found_is_400(self, client, book_and_membership):
        """Backwards compat — unknown ingredient_id 400s as before."""
        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Missing Ingredient Recipe",
                "ingredients": [
                    {
                        "ingredient_id": "nonexistent-id",
                        "quantity": 1,
                        "unit": "cup",
                    }
                ],
            },
        )
        assert response.status_code == 400

    def test_name_lowercased_and_stripped(
        self, client, mock_db, book_and_membership
    ):
        """`  BUTTER  ` and `butter` should resolve to the same canonical row."""
        existing = MockIngredient(
            id=str(uuid.uuid4()), canonical_name="butter", is_canonical=True
        )
        mock_db.set_find_by(Ingredient, existing, canonical_name="butter")

        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Canonical Normalization",
                "ingredients": [
                    {"name": "  BUTTER  ", "quantity": 1, "unit": "tbsp"}
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "butter"


class TestUpdateRecipeNameOrId:
    def _setup_recipe(self, mock_db, book_id, recipe_id, ing_tuple=None):
        """Wire a Recipe + a predictable query chain.

        The update path calls `db.query` twice: once for the version
        snapshot's `max(version_number).scalar()` and once for the joined
        ingredient fetch on the way out. A `side_effect` list returns a
        distinct MockQuery for each call so scalar() gets None (→ 0) and
        .all() gets the (ri, ingredient) tuple we want.
        """
        recipe = MockRecipe(
            id=recipe_id,
            name="Existing",
            recipe_book_id=book_id,
            tags=[],
        )
        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.db.query.side_effect = [
            MockQuery([]),  # max_version
            MockQuery([ing_tuple] if ing_tuple else []),  # joined fetch
        ]
        return recipe

    def test_update_accepts_name_only(
        self, client, mock_db, mock_user, book_and_membership
    ):
        from conftest import MockRecipeIngredient

        recipe_id = str(uuid.uuid4())
        created_ri = MockRecipeIngredient(recipe_id=recipe_id)
        created_ingredient = MockIngredient(canonical_name="paprika")
        self._setup_recipe(
            mock_db,
            book_and_membership,
            recipe_id,
            ing_tuple=(created_ri, created_ingredient),
        )

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={
                "ingredients": [
                    {"name": "paprika", "quantity": 1, "unit": "tsp"}
                ],
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data["ingredients"]) == 1
        assert (
            data["ingredients"][0]["ingredient"]["canonical_name"] == "paprika"
        )

    def test_update_rejects_neither_id_nor_name(
        self, client, mock_db, mock_user, book_and_membership
    ):
        recipe_id = str(uuid.uuid4())
        self._setup_recipe(mock_db, book_and_membership, recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={
                "ingredients": [
                    {"quantity": 1, "unit": "tsp"}
                ],
            },
        )
        assert response.status_code == 400
