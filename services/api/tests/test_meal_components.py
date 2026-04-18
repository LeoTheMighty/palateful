"""Tests for Meal component + favorite endpoints (mcv-3 scope).

  POST   /v1/meals/{id}/recipes                 (AddRecipeToMeal)
  DELETE /v1/meals/{id}/recipes/{recipe_id}     (RemoveRecipeFromMeal)
  POST   /v1/meals/{id}/reorder                 (ReorderMealComponents)
  POST   /v1/meals/{id}/favorite                (FavoriteMeal)
  DELETE /v1/meals/{id}/favorite                (UnfavoriteMeal)

Plus MealService unit tests for the mcv-3 methods.
"""

from unittest.mock import MagicMock

import pytest
from conftest import (
    MockModel,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
)

from utils.services.meal_service import (
    ComponentDuplicateError,
    ComponentNotFoundError,
    ComponentUnreadableError,
    MealService,
    MinComponentsError,
    ReorderMismatchError,
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
        defaults = {"user_id": "u", "meal_id": "meal-1"}
        defaults.update(kwargs)
        super().__init__(**defaults)


def _owner():
    return MockRecipeBookUser(role="owner")


def _build_component(recipe_id="r1", name="R", order=0, book_id="book-1"):
    book = MockRecipeBook(id=book_id, name="Dinners")
    recipe = MockRecipe(
        id=recipe_id,
        name=name,
        recipe_book_id=book_id,
        recipe_book=book,
    )
    return _MockMealRecipe(
        recipe=recipe, recipe_id=recipe_id, order_index=order
    )


def _build_service():
    session = MagicMock()
    session.query.return_value = MockQuery()
    return MealService(session), session


# ---------------------------------------------------------------------------
# MealService — add/remove/reorder/set_favorite unit tests
# ---------------------------------------------------------------------------


class TestAddComponent:
    def test_happy_with_explicit_order(self):
        service, session = _build_service()
        meal = _MockMeal()
        # 1) duplicate-check query (empty)
        # 2) _ensure_components_readable: Recipe.in_
        # 3) _readable_book_ids
        session.query.side_effect = [
            MockQuery([]),
            MockQuery([
                MockRecipe(
                    id="r-new",
                    recipe_book_id="book-1",
                    recipe_book=MockRecipeBook(id="book-1"),
                )
            ]),
            MockQuery([("book-1",)]),
        ]
        result = service.add_component(
            meal=meal, recipe_id="r-new", order_index=5, user_id="u"
        )
        assert result.order_index == 5

    def test_happy_with_default_order(self):
        service, session = _build_service()
        meal = _MockMeal()
        existing = _MockMealRecipe(order_index=3)
        session.query.side_effect = [
            MockQuery([]),  # duplicate-check
            MockQuery([
                MockRecipe(
                    id="r-new",
                    recipe_book_id="book-1",
                    recipe_book=MockRecipeBook(id="book-1"),
                )
            ]),
            MockQuery([("book-1",)]),
            MockQuery([existing]),  # max_row lookup
        ]
        result = service.add_component(
            meal=meal, recipe_id="r-new", order_index=None, user_id="u"
        )
        assert result.order_index == 4

    def test_happy_default_order_when_empty(self):
        service, session = _build_service()
        meal = _MockMeal()
        session.query.side_effect = [
            MockQuery([]),
            MockQuery([
                MockRecipe(
                    id="r-new",
                    recipe_book_id="book-1",
                    recipe_book=MockRecipeBook(id="book-1"),
                )
            ]),
            MockQuery([("book-1",)]),
            MockQuery([]),  # no existing rows
        ]
        result = service.add_component(
            meal=meal, recipe_id="r-new", order_index=None, user_id="u"
        )
        assert result.order_index == 0

    def test_duplicate_raises(self):
        service, session = _build_service()
        meal = _MockMeal()
        session.query.return_value = MockQuery([_MockMealRecipe()])
        with pytest.raises(ComponentDuplicateError):
            service.add_component(
                meal=meal, recipe_id="r1", order_index=None, user_id="u"
            )

    def test_unreadable_raises(self):
        service, session = _build_service()
        meal = _MockMeal()
        # No duplicate, but recipe not found
        session.query.side_effect = [
            MockQuery([]),
            MockQuery([]),
            MockQuery([]),
        ]
        with pytest.raises(ComponentUnreadableError):
            service.add_component(
                meal=meal, recipe_id="r-x", order_index=None, user_id="u"
            )


class TestRemoveComponent:
    def test_happy_at_three(self):
        service, session = _build_service()
        meal = _MockMeal()
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
            _MockMealRecipe(recipe_id="r3"),
        ]
        session.query.return_value = MockQuery(rows)
        service.remove_component(meal=meal, recipe_id="r3")
        session.delete.assert_called_once()

    def test_rejects_at_two(self):
        service, session = _build_service()
        meal = _MockMeal()
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
        ]
        session.query.return_value = MockQuery(rows)
        with pytest.raises(MinComponentsError):
            service.remove_component(meal=meal, recipe_id="r1")

    def test_not_found_raises(self):
        service, session = _build_service()
        meal = _MockMeal()
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
            _MockMealRecipe(recipe_id="r3"),
        ]
        session.query.return_value = MockQuery(rows)
        with pytest.raises(ComponentNotFoundError):
            service.remove_component(meal=meal, recipe_id="r-ghost")


class TestReorderComponents:
    def test_happy(self):
        service, session = _build_service()
        meal = _MockMeal()
        rows = [
            _MockMealRecipe(recipe_id="r1", order_index=0),
            _MockMealRecipe(recipe_id="r2", order_index=1),
            _MockMealRecipe(recipe_id="r3", order_index=2),
        ]
        session.query.return_value = MockQuery(rows)
        service.reorder_components(
            meal=meal, recipe_ids=["r3", "r1", "r2"]
        )
        order_by_id = {str(r.recipe_id): r.order_index for r in rows}
        assert order_by_id == {"r1": 1, "r2": 2, "r3": 0}

    def test_mismatch_rejects_missing_id(self):
        service, session = _build_service()
        meal = _MockMeal()
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
        ]
        session.query.return_value = MockQuery(rows)
        with pytest.raises(ReorderMismatchError):
            service.reorder_components(
                meal=meal, recipe_ids=["r1", "r-ghost"]
            )

    def test_mismatch_rejects_wrong_length(self):
        service, session = _build_service()
        meal = _MockMeal()
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
            _MockMealRecipe(recipe_id="r3"),
        ]
        session.query.return_value = MockQuery(rows)
        with pytest.raises(ReorderMismatchError):
            service.reorder_components(
                meal=meal, recipe_ids=["r1", "r2"]
            )


class TestSetFavorite:
    def test_favorite_new(self):
        service, session = _build_service()
        session.query.return_value = MockQuery([])
        assert service.set_favorite(
            user_id="u", meal_id="m", favorite=True
        ) is True
        session.add.assert_called_once()

    def test_favorite_idempotent_when_already_favorite(self):
        service, session = _build_service()
        session.query.return_value = MockQuery([_MockMealFavorite()])
        assert service.set_favorite(
            user_id="u", meal_id="m", favorite=True
        ) is False
        session.add.assert_not_called()

    def test_unfavorite_existing(self):
        service, session = _build_service()
        session.query.return_value = MockQuery([_MockMealFavorite()])
        assert service.set_favorite(
            user_id="u", meal_id="m", favorite=False
        ) is True
        session.delete.assert_called_once()

    def test_unfavorite_idempotent_when_not_favorited(self):
        service, session = _build_service()
        session.query.return_value = MockQuery([])
        assert service.set_favorite(
            user_id="u", meal_id="m", favorite=False
        ) is False
        session.delete.assert_not_called()


# ---------------------------------------------------------------------------
# HTTP tests
# ---------------------------------------------------------------------------


def _meal_with(components):
    return _MockMeal(components=components)


class TestAddRecipeToMealEndpoint:
    def test_happy(self, client, mock_db, mock_user):
        meal = _meal_with([_build_component("r1"), _build_component("r2", "R2", 1)])
        # Queries:
        # 1) get_with_components (require_meal_write)
        # 2) user_has_book_write
        # 3) duplicate check on MealRecipe
        # 4) _ensure_components_readable → Recipe.in_
        # 5) _readable_book_ids
        # 6) max order_index (none provided)  → will be None so skipped if we pass explicit
        # 7) get_with_components (re-fetch)
        # 8) hydrate → _readable_book_ids
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([]),  # no duplicate
            MockQuery([
                MockRecipe(
                    id="r3",
                    recipe_book_id="book-1",
                    recipe_book=MockRecipeBook(id="book-1"),
                )
            ]),
            MockQuery([("book-1",)]),
            MockQuery([meal]),
            MockQuery([("book-1",)]),
            MockQuery([]),  # is_favorited → MealFavorite
        ]
        response = client.post(
            "/v1/meals/meal-1/recipes",
            json={"recipe_id": "r3", "order_index": 2},
        )
        assert response.status_code == 201

    def test_duplicate_409(self, client, mock_db, mock_user):
        meal = _meal_with([_build_component("r1"), _build_component("r2", "R2", 1)])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([_MockMealRecipe()]),  # duplicate
        ]
        response = client.post(
            "/v1/meals/meal-1/recipes",
            json={"recipe_id": "r1", "order_index": 2},
        )
        assert response.status_code == 409

    def test_unreadable_recipe_404(self, client, mock_db, mock_user):
        meal = _meal_with([_build_component("r1"), _build_component("r2", "R2", 1)])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([]),  # no duplicate
            MockQuery([]),  # recipe not found
            MockQuery([]),
        ]
        response = client.post(
            "/v1/meals/meal-1/recipes",
            json={"recipe_id": "r-missing"},
        )
        assert response.status_code == 404

    def test_non_writer_403(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([MockRecipeBookUser(role="viewer")]),
        ]
        response = client.post(
            "/v1/meals/meal-1/recipes",
            json={"recipe_id": "r3", "order_index": 0},
        )
        assert response.status_code == 403


class TestRemoveRecipeFromMealEndpoint:
    def test_happy_at_three(self, client, mock_db, mock_user):
        meal = _meal_with([
            _build_component("r1"),
            _build_component("r2", "R2", 1),
            _build_component("r3", "R3", 2),
        ])
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
            _MockMealRecipe(recipe_id="r3"),
        ]
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery(rows),  # service.remove_component fetches rows
            MockQuery([meal]),  # re-fetch
            MockQuery([("book-1",)]),
            MockQuery([]),  # is_favorited → MealFavorite
        ]
        response = client.delete("/v1/meals/meal-1/recipes/r3")
        assert response.status_code == 200

    def test_at_two_rejects_422(self, client, mock_db, mock_user):
        meal = _meal_with([_build_component("r1"), _build_component("r2", "R2", 1)])
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
        ]
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery(rows),
        ]
        response = client.delete("/v1/meals/meal-1/recipes/r1")
        assert response.status_code == 422

    def test_component_not_found_404(self, client, mock_db, mock_user):
        meal = _meal_with([])
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
            _MockMealRecipe(recipe_id="r3"),
        ]
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery(rows),
        ]
        response = client.delete("/v1/meals/meal-1/recipes/ghost")
        assert response.status_code == 404

    def test_non_writer_403(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([MockRecipeBookUser(role="viewer")]),
        ]
        response = client.delete("/v1/meals/meal-1/recipes/r1")
        assert response.status_code == 403


class TestReorderMealComponentsEndpoint:
    def test_happy(self, client, mock_db, mock_user):
        meal = _meal_with([
            _build_component("r1"),
            _build_component("r2", "R2", 1),
            _build_component("r3", "R3", 2),
        ])
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
            _MockMealRecipe(recipe_id="r3"),
        ]
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery(rows),      # reorder_components fetch
            MockQuery([meal]),    # re-fetch
            MockQuery([("book-1",)]),
            MockQuery([]),        # is_favorited → MealFavorite
        ]
        response = client.post(
            "/v1/meals/meal-1/reorder",
            json={"recipe_ids": ["r3", "r2", "r1"]},
        )
        assert response.status_code == 200

    def test_mismatch_422(self, client, mock_db, mock_user):
        meal = _meal_with([])
        rows = [
            _MockMealRecipe(recipe_id="r1"),
            _MockMealRecipe(recipe_id="r2"),
        ]
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery(rows),
        ]
        response = client.post(
            "/v1/meals/meal-1/reorder",
            json={"recipe_ids": ["r1", "r-ghost"]},
        )
        assert response.status_code == 422

    def test_schema_rejects_duplicates(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/meals/meal-1/reorder",
            json={"recipe_ids": ["r1", "r1"]},
        )
        assert response.status_code == 422

    def test_schema_rejects_one_id(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/meals/meal-1/reorder",
            json={"recipe_ids": ["r1"]},
        )
        assert response.status_code == 422

    def test_non_writer_403(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([MockRecipeBookUser(role="viewer")]),
        ]
        response = client.post(
            "/v1/meals/meal-1/reorder",
            json={"recipe_ids": ["r1", "r2"]},
        )
        assert response.status_code == 403


class TestFavoriteEndpoints:
    def test_favorite_first_time(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),      # require_meal_read → get_with_components
            MockQuery([_owner()]),  # user_has_book_read
            MockQuery([]),          # existing favorite? none
        ]
        response = client.post("/v1/meals/meal-1/favorite")
        assert response.status_code == 201
        assert response.json()["is_favorite"] is True

    def test_favorite_idempotent(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([_MockMealFavorite()]),  # already favorited
        ]
        response = client.post("/v1/meals/meal-1/favorite")
        assert response.status_code == 201
        assert response.json()["is_favorite"] is True

    def test_unfavorite_existing(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([_MockMealFavorite()]),
        ]
        response = client.delete("/v1/meals/meal-1/favorite")
        assert response.status_code == 200
        assert response.json()["is_favorite"] is False

    def test_unfavorite_idempotent(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([]),
        ]
        response = client.delete("/v1/meals/meal-1/favorite")
        assert response.status_code == 200

    def test_favorite_requires_read_membership(self, client, mock_db, mock_user):
        meal = _meal_with([])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([]),  # not a member
        ]
        response = client.post("/v1/meals/meal-1/favorite")
        assert response.status_code == 403
