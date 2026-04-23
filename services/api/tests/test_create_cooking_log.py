"""mcal-6: `POST /v1/cooking-logs` handler.

Covers:
  * Recipe event → 1 row, `recipe_id` set.
  * Meal event  → 1 parent + N children with `parent_meal_log_id`.
  * Direct recipe_id → 1 row, no fan-out.
  * XOR enforcement (both / neither set → 422).
  * 404 on missing event / recipe; 422 on free-text event.

aam-21: handler is now `AsyncEndpoint`; meal-event fan-out no longer
reads `event.meal` (lazy-load on the async engine would trip
MissingGreenlet). Instead it `await self.db.execute(select(Meal)...)`
with explicit selectinload. Tests for that branch stub
`mock_async_db.db.execute` to return the meal.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from conftest import MockExecuteResult, MockMealEvent, MockModel, MockRecipe


class MockMeal(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "name": "Kale Salad Meal",
            "components": [],
            "recipe_book_id": str(uuid.uuid4()),
            "share_token": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockMealRecipe(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "meal_id": str(uuid.uuid4()),
            "recipe_id": str(uuid.uuid4()),
            "order_index": 0,
            "recipe": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class TestXor:
    def test_both_ids_rejected(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/cooking-logs",
            json={
                "meal_event_id": str(uuid.uuid4()),
                "recipe_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 422

    def test_neither_id_rejected(self, client, mock_async_db, mock_user):
        response = client.post("/v1/cooking-logs", json={})
        assert response.status_code == 422


class TestRecipeEvent:
    def test_recipe_event_produces_single_log(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent

        event = MockMealEvent(
            id=str(uuid.uuid4()),
            owner_id=mock_user.id,
            recipe_id=str(uuid.uuid4()),
            meal_id=None,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)

        response = client.post(
            "/v1/cooking-logs",
            json={"meal_event_id": event.id, "notes": "medium rare"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["recipe_id"] == event.recipe_id
        assert data["meal_id"] is None
        assert data["child_log_ids"] == []


class TestMealEvent:
    def test_meal_event_fans_out_to_children(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent

        r1 = MockRecipe(id=str(uuid.uuid4()))
        r2 = MockRecipe(id=str(uuid.uuid4()))
        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[
                MockMealRecipe(recipe=r1, order_index=0),
                MockMealRecipe(recipe=r2, order_index=1),
            ],
        )
        event = MockMealEvent(
            id=str(uuid.uuid4()),
            owner_id=mock_user.id,
            recipe_id=None,
            meal_id=meal.id,
            meal=meal,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        # Handler's explicit `select(Meal).options(selectinload(...))` uses
        # `result.scalars().first()` to get the meal — return the meal
        # from the stubbed execute.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[meal])

        response = client.post(
            "/v1/cooking-logs",
            json={"meal_event_id": event.id, "scale_factor": "1.5"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["meal_id"] == meal.id
        assert data["recipe_id"] is None
        assert len(data["child_log_ids"]) == 2

    def test_archived_component_skipped_in_fanout(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent

        r1 = MockRecipe(id=str(uuid.uuid4()))
        r2 = MockRecipe(id=str(uuid.uuid4()))
        r2.archived_at = datetime.now(UTC)
        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[
                MockMealRecipe(recipe=r1, order_index=0),
                MockMealRecipe(recipe=r2, order_index=1),
            ],
        )
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe_id=None, meal_id=meal.id, meal=meal,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[meal])

        response = client.post(
            "/v1/cooking-logs", json={"meal_event_id": event.id}
        )
        assert response.status_code == 201
        assert len(response.json()["child_log_ids"]) == 1

    def test_meal_event_with_null_component_recipe_skipped(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_event import MealEvent

        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[MockMealRecipe(recipe=None, order_index=0)],
        )
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe_id=None, meal_id=meal.id, meal=meal,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[meal])

        response = client.post(
            "/v1/cooking-logs", json={"meal_event_id": event.id}
        )
        assert response.status_code == 201
        assert response.json()["child_log_ids"] == []

    def test_meal_event_without_meal_relationship_has_no_children(
        self, client, mock_async_db, mock_user
    ):
        """Defensive: if meal_id is set but the meal row is gone,
        the parent row still writes — fan-out is empty."""
        from utils.models.meal_event import MealEvent

        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe_id=None, meal_id=str(uuid.uuid4()),
            meal=None,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        # Meal lookup returns empty — fan-out should be empty.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])

        response = client.post(
            "/v1/cooking-logs", json={"meal_event_id": event.id}
        )
        assert response.status_code == 201
        assert response.json()["child_log_ids"] == []


class TestDirectRecipe:
    def test_direct_recipe_produces_single_log(self, client, mock_async_db, mock_user):
        from utils.models.recipe import Recipe

        recipe = MockRecipe(id=str(uuid.uuid4()))
        mock_async_db.set_find_by(Recipe, recipe, id=recipe.id)

        response = client.post(
            "/v1/cooking-logs",
            json={"recipe_id": recipe.id, "cooked_at": "2026-04-18T18:00:00Z"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["recipe_id"] == recipe.id
        assert data["meal_id"] is None

    def test_404_on_missing_recipe(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/cooking-logs", json={"recipe_id": str(uuid.uuid4())}
        )
        assert response.status_code == 404


class TestErrors:
    def test_404_on_missing_event(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/cooking-logs",
            json={"meal_event_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_422_on_freetext_event(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent

        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe_id=None, meal_id=None,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)

        response = client.post(
            "/v1/cooking-logs", json={"meal_event_id": event.id}
        )
        assert response.status_code == 422
