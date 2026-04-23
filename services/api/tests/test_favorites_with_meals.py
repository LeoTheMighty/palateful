"""md-3: `/v1/favorites` extension — favorited_meals key.

Response is additive:
* `items` / `total` remain the recipe favorites (unchanged).
* `favorited_meals` is populated from `meal_favorites`, sorted by the
  favorite row's `created_at` (most recent first).

Old clients ignore the new key; new clients iterate both arrays for the
home favorites carousel.

aam-10: handler converted to `AsyncEndpoint` (cross-domain — recipe
endpoint depends on the now-async meal `_response.py` builders). Tests
configure `mock_async_db.db.execute.side_effect` instead of
`mock_db.db.query.side_effect`.
"""

from conftest import (
    MockExecuteResult,
    MockModel,
    MockRecipe,
    MockRecipeBook,
    MockUserFavorite,
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


class _MockMealFavorite(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "user_id": "user-1",
            "meal_id": "meal-1",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _component(recipe_id="r1", name="R"):
    book = MockRecipeBook(id="book-1", name="Dinners")
    recipe = MockRecipe(
        id=recipe_id, name=name, recipe_book_id="book-1", recipe_book=book
    )
    return _MockMealRecipe(recipe_id=recipe_id, recipe=recipe, order_index=0)


class TestListFavoritesWithMeals:
    """Covers the additive `favorited_meals` key."""

    def test_empty_meal_favorites_returns_empty_key(
        self, client, mock_async_db, mock_user
    ):
        """Zero-Meal-favorite user sees `favorited_meals: []` — same shape
        for new clients, ignored by old ones."""
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        resp = client.get("/v1/favorites")
        assert resp.status_code == 200
        data = resp.json()
        assert "favorited_meals" in data
        assert data["favorited_meals"] == []
        # additive: items/total unchanged
        assert data["items"] == []
        assert data["total"] == 0

    def test_with_favorited_meal(self, client, mock_async_db, mock_user):
        meal = _MockMeal(
            components=[_component("r1"), _component("r2", "Kale")]
        )
        fav = _MockMealFavorite(user_id=str(mock_user.id), meal_id="meal-1")
        # Execute order: 1) recipe favorites 2) meal favorites
        # 3) hydrate → _readable_book_ids
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),               # recipe favorites — none
            MockExecuteResult(items=[(fav, meal)]),    # meal favorites
            MockExecuteResult(items=[("book-1",)]),    # hydrate → readable books
        ]
        resp = client.get("/v1/favorites")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["favorited_meals"]) == 1
        assert data["favorited_meals"][0]["id"] == "meal-1"
        assert data["favorited_meals"][0]["component_count"] == 2

    def test_mixed_recipes_and_meals(self, client, mock_async_db, mock_user):
        recipe = MockRecipe(name="Favorite Pasta", tags=["italian"])
        r_fav = MockUserFavorite(user_id=str(mock_user.id), recipe_id=str(recipe.id))
        meal = _MockMeal(
            components=[_component("r1"), _component("r2", "Kale")]
        )
        m_fav = _MockMealFavorite(
            user_id=str(mock_user.id), meal_id="meal-1"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[(r_fav, recipe)]),
            MockExecuteResult(items=[(m_fav, meal)]),
            MockExecuteResult(items=[("book-1",)]),
        ]
        resp = client.get("/v1/favorites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1  # recipe total unchanged
        assert len(data["favorited_meals"]) == 1
