"""Tests for bugs-imp-ing-5 — recipe create/update accept name or id.

Post-`epic-ingredients-string-simplification` the shared `resolve_ingredient`
helper is retired; each endpoint handles the branch inline:
* `ingredient_id` alone → existing canonical lookup path (unchanged).
* `name` alone → insert a fresh `ingredients` row (no find-or-create).
* neither present → 400 / INGREDIENT_INPUT_REQUIRED.
`ingredient_id` wins when both are supplied.
"""

import uuid

import pytest
from conftest import (
    MockExecuteResult,
    MockIngredient,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
)
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser


@pytest.fixture
def book_and_membership(mock_async_db, mock_user):
    """Authenticated owner membership on a recipe book."""
    book_id = "test-book-id"
    book = MockRecipeBook(id=book_id)
    membership = MockRecipeBookUser(
        user_id=str(mock_user.id),
        recipe_book_id=book_id,
        role="owner",
    )
    mock_async_db.set_find_by(
        RecipeBookUser,
        membership,
        user_id=str(mock_user.id),
        recipe_book_id=book_id,
    )
    mock_async_db.set_find_by(RecipeBook, book, id=book_id)
    return book_id


class TestCreateRecipeNameOrId:
    def test_name_only_creates_fresh_ingredient_row(
        self, client, mock_async_db, book_and_membership
    ):
        """Name-only input inserts a fresh `ingredients` row — no matching."""
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

    def test_repeated_names_create_distinct_rows(
        self, client, mock_async_db, book_and_membership
    ):
        """Post-epic-ingredients-string-simplification: repeating the same
        name across ingredients always stages a new row — no find-or-create,
        no cross-recipe identity."""
        response = client.post(
            f"/v1/recipe-books/{book_and_membership}/recipes",
            json={
                "name": "Olive Oil × 2",
                "ingredients": [
                    {"name": "olive oil", "quantity": 1, "unit": "tbsp"},
                    {"name": "olive oil", "quantity": 2, "unit": "tbsp"},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["ingredients"]) == 2
        # Both rows carry the same canonical_name — no merging, two lines.
        assert data["ingredients"][0]["ingredient"]["canonical_name"] == "olive oil"
        assert data["ingredients"][1]["ingredient"]["canonical_name"] == "olive oil"
        # Confirm two distinct Ingredient instances were staged: find-or-create
        # would have added only one. (The in-memory mock_async_db leaves flush as a
        # no-op so DB-assigned IDs aren't observable via response; counting
        # adds is the direct proof.)
        added_ingredients = [
            call.args[0]
            for call in mock_async_db.db.add.call_args_list
            if isinstance(call.args[0], Ingredient)
        ]
        assert len(added_ingredients) == 2
        assert added_ingredients[0] is not added_ingredients[1]

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
        self, client, mock_async_db, book_and_membership
    ):
        """Backwards compat — existing clients supplying only ingredient_id."""
        ing_id = str(uuid.uuid4())
        existing = MockIngredient(id=ing_id, canonical_name="flour")
        mock_async_db.set_find_by(Ingredient, existing, id=ing_id)

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
        self, client, mock_async_db, book_and_membership
    ):
        """When both inputs arrive, ingredient_id wins (guards against name drift)."""
        ing_id = str(uuid.uuid4())
        existing = MockIngredient(id=ing_id, canonical_name="sugar")
        mock_async_db.set_find_by(Ingredient, existing, id=ing_id)

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
        self, client, mock_async_db, book_and_membership
    ):
        """`  BUTTER  ` gets stored as `butter` (lowercased + stripped),
        even though a separate fresh row is created per the epic."""
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
    def _setup_recipe(self, mock_async_db, book_id, recipe_id, ing_tuple=None):
        """Wire a Recipe + a predictable execute chain.

        The async update path awaits `db.execute` twice when params carry
        ingredients: once for the version snapshot's
        `select(func.max(RecipeVersion.version_number)).scalar()` and once
        for the joined ingredient fetch on the way out. A `side_effect`
        list returns a distinct MockExecuteResult for each call so
        scalar() gets None (→ 0) and .all() gets the (ri, ingredient)
        tuple we want.
        """
        recipe = MockRecipe(
            id=recipe_id,
            name="Existing",
            recipe_book_id=book_id,
            tags=[],
        )
        mock_async_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),  # max_version
            MockExecuteResult(items=[ing_tuple] if ing_tuple else []),  # joined fetch
        ]
        return recipe

    def test_update_accepts_name_only(
        self, client, mock_async_db, mock_user, book_and_membership
    ):
        from conftest import MockRecipeIngredient

        recipe_id = str(uuid.uuid4())
        created_ri = MockRecipeIngredient(recipe_id=recipe_id)
        created_ingredient = MockIngredient(canonical_name="paprika")
        self._setup_recipe(
            mock_async_db,
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
        self, client, mock_async_db, mock_user, book_and_membership
    ):
        recipe_id = str(uuid.uuid4())
        self._setup_recipe(mock_async_db, book_and_membership, recipe_id)

        response = client.put(
            f"/v1/recipes/{recipe_id}",
            json={
                "ingredients": [
                    {"quantity": 1, "unit": "tsp"}
                ],
            },
        )
        assert response.status_code == 400
