"""md-2: Tests for `GET /v1/recipes/{recipe_id}/meals`.

aam-10: handler converted to `AsyncEndpoint` (recipe-domain crossover —
needed because `_response.build_meal_summary` is now async). Recipe +
membership lookups still go through `database.find_by(...)`; the meals
list goes through `db.execute(select(Meal)...)`. Per-meal hydration of
the readable-books set is the third execute call (one per request, not
per meal).
"""

from datetime import UTC, datetime

from conftest import (
    MockExecuteResult,
    MockModel,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
)


class _MockMealRecipe(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "meal_id": "meal-1",
            "recipe_id": "recipe-1",
            "order_index": 0,
            "recipe": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class _MockMeal(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "id": "meal-1",
            "name": "Kale Salad Meal",
            "description": None,
            "recipe_book_id": "book-1",
            "share_token": None,
            "components": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _component(recipe_id, name, book_id="book-1"):
    book = MockRecipeBook(id=book_id, name="Dinners")
    recipe = MockRecipe(
        id=recipe_id,
        name=name,
        recipe_book_id=book_id,
        recipe_book=book,
    )
    return _MockMealRecipe(
        recipe_id=recipe_id, recipe=recipe, order_index=0
    )


class TestListMealsUsingRecipe:
    """GET /v1/recipes/{recipe_id}/meals."""

    def test_happy_returns_meals(self, client, mock_async_db, mock_user):
        recipe = MockRecipe(id="recipe-1", recipe_book_id="book-1")
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        mock_async_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_async_db.set_find_by(
            RecipeBookUser,
            MockRecipeBookUser(role="owner"),
            user_id=mock_user.id,
            recipe_book_id="book-1",
        )
        meal = _MockMeal(
            components=[_component("recipe-1", "Lemon Dressing"), _component("r2", "Kale")]
        )
        # Execute order:
        # 1) Meal list (with selectinload on components)
        # 2) hydrate each meal → _readable_book_ids (single call — list
        #    handler hoists this; per-meal loop reuses the set in memory).
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[("book-1",)]),
        ]

        resp = client.get("/v1/recipes/recipe-1/meals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "meal-1"

    def test_empty_list_not_404(self, client, mock_async_db, mock_user):
        recipe = MockRecipe(id="recipe-1", recipe_book_id="book-1")
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        mock_async_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_async_db.set_find_by(
            RecipeBookUser,
            MockRecipeBookUser(role="owner"),
            user_id=mock_user.id,
            recipe_book_id="book-1",
        )
        # Empty meals list → no per-meal hydration call fires.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        resp = client.get("/v1/recipes/recipe-1/meals")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_recipe_not_found_returns_404(self, client, mock_async_db, mock_user):
        # set_find_by returns None by default — recipe not found.
        resp = client.get("/v1/recipes/nonexistent/meals")
        assert resp.status_code == 404

    def test_no_book_membership_returns_403(self, client, mock_async_db, mock_user):
        recipe = MockRecipe(id="recipe-1", recipe_book_id="book-private")
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        mock_async_db.set_find_by(Recipe, recipe, id="recipe-1")
        # RecipeBookUser default None → 403
        mock_async_db.set_find_by(
            RecipeBookUser,
            None,
            user_id=mock_user.id,
            recipe_book_id="book-private",
        )
        resp = client.get("/v1/recipes/recipe-1/meals")
        assert resp.status_code == 403

    def test_archived_recipe_still_queryable(self, client, mock_async_db, mock_user):
        """If you archived Dressing, you may still want to see that it was
        part of Kale Salad Meal."""
        recipe = MockRecipe(
            id="recipe-1",
            recipe_book_id="book-1",
            archived_at=datetime.now(UTC),
        )
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        mock_async_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_async_db.set_find_by(
            RecipeBookUser,
            MockRecipeBookUser(role="owner"),
            user_id=mock_user.id,
            recipe_book_id="book-1",
        )
        meal = _MockMeal(components=[_component("recipe-1", "Dressing"), _component("r2", "Kale")])
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[("book-1",)]),
        ]
        resp = client.get("/v1/recipes/recipe-1/meals")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_cross_book_visibility(self, client, mock_async_db, mock_user):
        """Recipe in Book A, Meal in Book B — both readable → Meal surfaces."""
        recipe = MockRecipe(id="recipe-1", recipe_book_id="book-a")
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        mock_async_db.set_find_by(Recipe, recipe, id="recipe-1")
        mock_async_db.set_find_by(
            RecipeBookUser,
            MockRecipeBookUser(role="viewer"),
            user_id=mock_user.id,
            recipe_book_id="book-a",
        )
        meal = _MockMeal(
            id="meal-in-b",
            recipe_book_id="book-b",
            components=[
                _component("recipe-1", "X", book_id="book-a"),
                _component("r2", "Y", book_id="book-b"),
            ],
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[("book-a",), ("book-b",)]),
        ]
        resp = client.get("/v1/recipes/recipe-1/meals")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["id"] == "meal-in-b"
