"""mcal-3 tests — meal_event endpoints accept `meal_id` XOR `recipe_id`.

Covers:
- XOR rejection: both-set → 422, code `MEAL_EVENT_RECIPE_XOR_MEAL`.
- Meal-mode create: happy path; 404 on missing Meal; 404 on archived Meal;
  403 on non-reader.
- Meal-mode patch: mode switch (Recipe → Meal clears recipe_id; Meal → Recipe
  clears meal_id); both-set reject at runtime; meal_summary rehydration.
- `meal_summary` hydration on create + update + get + list. Mixed-event lists
  keep recipe-only events byte-identical to the pre-epic shape.
"""

import uuid
from datetime import datetime, timezone

from conftest import (
    MockExecuteResult,
    MockCalendar,
    MockMealEvent,
    MockModel,
    MockQuery,
    MockRecipe,
    MockRecipeBookUser,
)


class MockMeal(MockModel):
    """Mock Meal for hydration tests."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Kale Salad Meal",
            "description": None,
            "recipe_book_id": str(uuid.uuid4()),
            "share_token": None,
            "components": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockMealRecipe(MockModel):
    """Mock MealRecipe (component row)."""

    def __init__(self, **kwargs):
        defaults = {
            "meal_id": str(uuid.uuid4()),
            "recipe_id": str(uuid.uuid4()),
            "order_index": 0,
            "recipe": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _make_meal_with_components(*, user_id, archived=False):
    """A Meal with 2 live component recipes tied to a book the user can read."""
    from utils.models.meal import Meal as MealModel
    from utils.models.recipe_book_user import RecipeBookUser

    book_id = str(uuid.uuid4())
    recipe_a = MockRecipe(
        id=str(uuid.uuid4()), name="Kale Salad", image_url="https://cdn/a.jpg",
        recipe_book_id=book_id,
    )
    recipe_a.recipe_book = None  # avoid attribute-error in book-archived branch
    recipe_b = MockRecipe(
        id=str(uuid.uuid4()), name="Lemon Dressing", image_url="https://cdn/b.jpg",
        recipe_book_id=book_id,
    )
    recipe_b.recipe_book = None
    components = [
        MockMealRecipe(recipe=recipe_a, order_index=0),
        MockMealRecipe(recipe=recipe_b, order_index=1),
    ]
    meal_id = str(uuid.uuid4())
    meal = MockMeal(id=meal_id, name="Kale Salad Meal", components=components, recipe_book_id=book_id)
    if archived:
        meal.archived_at = datetime.now(timezone.utc)
    return meal, book_id, MealModel, RecipeBookUser


# ---------------------------------------------------------------------------
# XOR rejection
# ---------------------------------------------------------------------------


class TestXorRejection:
    def test_create_rejects_both_recipe_id_and_meal_id(self, client, mock_async_db, mock_user):
        body = {
            "title": "Tuesday Dinner",
            "scheduled_at": "2026-05-01T19:00:00Z",
            "meal_type": "dinner",
            "calendar_id": str(uuid.uuid4()),
            "recipe_id": str(uuid.uuid4()),
            "meal_id": str(uuid.uuid4()),
        }
        response = client.post("/v1/meal-events", json=body)
        assert response.status_code == 422
        assert response.json()["error_code"] == 135

    def test_patch_rejects_both_recipe_id_and_meal_id(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent

        event_id = str(uuid.uuid4())
        calendar = MockCalendar(id=str(uuid.uuid4()), owner_id=mock_user.id)
        event = MockMealEvent(
            id=event_id, owner_id=mock_user.id, calendar_id=calendar.id
        )
        mock_async_db.set_find_by(MealEvent, event, id=event_id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[event])

        body = {
            "recipe_id": str(uuid.uuid4()),
            "meal_id": str(uuid.uuid4()),
        }
        response = client.put(f"/v1/meal-events/{event_id}", json=body)
        assert response.status_code == 422
        assert response.json()["error_code"] == 135


# ---------------------------------------------------------------------------
# Create in Meal mode
# ---------------------------------------------------------------------------


class TestCreateMealMode:
    def test_create_meal_event_with_meal_id_hydrates_meal_summary(
        self, client, mock_async_db, mock_user
    ):
        meal, book_id, MealModel, RecipeBookUser = _make_meal_with_components(
            user_id=mock_user.id
        )
        # MealService.get_with_components uses db.query(Meal) — configure that.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[meal])
        mock_async_db.set_find_by(
            RecipeBookUser, MockRecipeBookUser(user_id=mock_user.id, recipe_book_id=book_id),
            user_id=mock_user.id, recipe_book_id=book_id,
        )

        body = {
            "title": "Tuesday Dinner",
            "scheduled_at": "2026-05-01T19:00:00Z",
            "meal_type": "dinner",
            "calendar_id": str(uuid.uuid4()),
            "meal_id": str(meal.id),
        }
        response = client.post("/v1/meal-events", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["meal_id"] == str(meal.id)
        assert data["meal_summary"]["name"] == "Kale Salad Meal"
        assert data["meal_summary"]["component_count"] == 2
        assert data["meal_summary"]["image_urls"] == [
            "https://cdn/a.jpg",
            "https://cdn/b.jpg",
        ]

    def test_create_with_missing_meal_returns_404(self, client, mock_async_db, mock_user):
        # MealService.get_with_components returns None for missing meal.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        body = {
            "title": "Dinner",
            "scheduled_at": "2026-05-01T19:00:00Z",
            "meal_type": "dinner",
            "calendar_id": str(uuid.uuid4()),
            "meal_id": str(uuid.uuid4()),
        }
        response = client.post("/v1/meal-events", json=body)
        assert response.status_code == 404

    def test_create_with_archived_meal_returns_404(self, client, mock_async_db, mock_user):
        meal, book_id, MealModel, RecipeBookUser = _make_meal_with_components(
            user_id=mock_user.id, archived=True
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[meal])
        mock_async_db.set_find_by(
            RecipeBookUser, MockRecipeBookUser(user_id=mock_user.id, recipe_book_id=book_id),
            user_id=mock_user.id, recipe_book_id=book_id,
        )
        body = {
            "title": "Dinner",
            "scheduled_at": "2026-05-01T19:00:00Z",
            "meal_type": "dinner",
            "calendar_id": str(uuid.uuid4()),
            "meal_id": str(meal.id),
        }
        response = client.post("/v1/meal-events", json=body)
        assert response.status_code == 404

    def test_create_when_user_lacks_book_read_returns_403(self, client, mock_async_db, mock_user):
        meal, book_id, MealModel, RecipeBookUser = _make_meal_with_components(
            user_id=mock_user.id
        )

        # MealService first loads the Meal (`get_with_components` ->
        # db.query(Meal)), then checks `user_has_book_read` via
        # db.query(RecipeBookUser). Route them by argument type.
        def _query_router(model):
            if model is MealModel:
                return MockExecuteResult(items=[meal])
            return MockExecuteResult(items=[])  # RecipeBookUser → empty → 403

        mock_async_db.db.execute.side_effect = _query_router

        body = {
            "title": "Dinner",
            "scheduled_at": "2026-05-01T19:00:00Z",
            "meal_type": "dinner",
            "calendar_id": str(uuid.uuid4()),
            "meal_id": str(meal.id),
        }
        response = client.post("/v1/meal-events", json=body)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Regression: recipe-only create still works
# ---------------------------------------------------------------------------


class TestRecipeOnlyRegression:
    def test_create_recipe_only_event_still_works(self, client, mock_async_db, mock_user):
        """mcal-3 must not regress the Recipe-only path."""
        from utils.models.recipe import Recipe

        recipe = MockRecipe(id=str(uuid.uuid4()), name="Pizza")
        mock_async_db.set_find_by(Recipe, recipe, id=recipe.id)

        body = {
            "title": "Friday Dinner",
            "scheduled_at": "2026-05-01T19:00:00Z",
            "meal_type": "dinner",
            "calendar_id": str(uuid.uuid4()),
            "recipe_id": recipe.id,
        }
        response = client.post("/v1/meal-events", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["recipe"]["name"] == "Pizza"
        assert data["meal_id"] is None
        assert data["meal_summary"] is None

    def test_create_freetext_event_still_works(self, client, mock_async_db, mock_user):
        body = {
            "title": "Takeout",
            "scheduled_at": "2026-05-01T19:00:00Z",
            "meal_type": "dinner",
            "calendar_id": str(uuid.uuid4()),
        }
        response = client.post("/v1/meal-events", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["recipe"] is None
        assert data["meal_id"] is None
        assert data["meal_summary"] is None


# ---------------------------------------------------------------------------
# Update / mode switch
# ---------------------------------------------------------------------------


class TestUpdateMealMode:
    def _setup_event(self, mock_async_db, mock_user, *, recipe_id=None, meal_id=None):
        from utils.models.meal_event import MealEvent

        event_id = str(uuid.uuid4())
        event = MockMealEvent(
            id=event_id,
            owner_id=mock_user.id,
            calendar_id=str(uuid.uuid4()),
            recipe_id=recipe_id,
            meal_id=meal_id,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event_id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[event])
        return event_id, event

    def test_switch_recipe_event_to_meal_clears_recipe_id(
        self, client, mock_async_db, mock_user
    ):
        meal, book_id, MealModel, RecipeBookUser = _make_meal_with_components(
            user_id=mock_user.id
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[meal])
        mock_async_db.set_find_by(
            RecipeBookUser, MockRecipeBookUser(user_id=mock_user.id, recipe_book_id=book_id),
            user_id=mock_user.id, recipe_book_id=book_id,
        )
        event_id, event = self._setup_event(
            mock_async_db, mock_user, recipe_id=str(uuid.uuid4())
        )
        # After the patch the hydration accesses event.meal directly (lazy);
        # fixture it so meal_summary populates without a DB roundtrip.
        event.meal = meal

        response = client.put(
            f"/v1/meal-events/{event_id}", json={"meal_id": str(meal.id)}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meal_id"] == str(meal.id)
        assert data["recipe"] is None  # cleared
        assert data["meal_summary"]["name"] == "Kale Salad Meal"

    def test_switch_meal_event_to_recipe_clears_meal_id(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.recipe import Recipe

        recipe = MockRecipe(id=str(uuid.uuid4()), name="Pizza")
        mock_async_db.set_find_by(Recipe, recipe, id=recipe.id)
        event_id, event = self._setup_event(
            mock_async_db, mock_user, meal_id=str(uuid.uuid4())
        )
        event.recipe = recipe

        response = client.put(
            f"/v1/meal-events/{event_id}", json={"recipe_id": recipe.id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meal_id"] is None
        assert data["meal_summary"] is None
        assert data["recipe"]["name"] == "Pizza"


# ---------------------------------------------------------------------------
# List + get hydration
# ---------------------------------------------------------------------------


class TestHydrationOnReads:
    def test_list_hydrates_meal_summary_on_meal_events(
        self, client, mock_async_db, mock_user
    ):
        meal, book_id, MealModel, _ = _make_meal_with_components(user_id=mock_user.id)
        recipe_event = MockMealEvent(
            id=str(uuid.uuid4()),
            owner_id=mock_user.id,
            recipe=MockRecipe(id=str(uuid.uuid4()), name="Pizza"),
            meal=None,
        )
        meal_event = MockMealEvent(
            id=str(uuid.uuid4()),
            owner_id=mock_user.id,
            recipe=None,
            meal_id=str(meal.id),
            meal=meal,
        )
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[recipe_event, meal_event])

        response = client.get("/v1/meal-events")
        assert response.status_code == 200
        items = response.json()["items"]
        by_has_meal = {item["id"]: item for item in items}
        # Recipe-only event: no meal_summary; same shape as pre-epic.
        assert by_has_meal[recipe_event.id]["meal_summary"] is None
        assert by_has_meal[recipe_event.id]["meal_id"] is None
        # Meal event: hydrated.
        assert by_has_meal[meal_event.id]["meal_summary"]["component_count"] == 2

    def test_get_meal_event_without_meal_has_null_meal_summary(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_event import MealEvent

        event_id = str(uuid.uuid4())
        event = MockMealEvent(id=event_id, owner_id=mock_user.id)
        mock_async_db.set_find_by(MealEvent, event, id=event_id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[event])

        response = client.get(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["meal_id"] is None
        assert data["meal_summary"] is None

    def test_get_meal_event_with_meal_hydrates_summary(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_event import MealEvent

        meal, book_id, MealModel, _ = _make_meal_with_components(user_id=mock_user.id)
        event_id = str(uuid.uuid4())
        event = MockMealEvent(
            id=event_id,
            owner_id=mock_user.id,
            recipe=None,
            meal_id=str(meal.id),
            meal=meal,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event_id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[event])

        response = client.get(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["meal_summary"]["name"] == "Kale Salad Meal"
        assert data["meal_summary"]["component_count"] == 2


# ---------------------------------------------------------------------------
# Build-meal-summary edge cases (unit)
# ---------------------------------------------------------------------------


class TestBuildMealSummaryEdges:
    def test_archived_recipe_component_drops_image_but_still_counts(self):
        from api.v1.meal_event._meal_binding import build_meal_summary

        r1 = MockRecipe(id=str(uuid.uuid4()), image_url="https://cdn/a.jpg")
        r1.recipe_book = None
        r2 = MockRecipe(id=str(uuid.uuid4()), image_url="https://cdn/b.jpg")
        r2.archived_at = datetime.now(timezone.utc)
        r2.recipe_book = None
        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[
                MockMealRecipe(recipe=r1, order_index=0),
                MockMealRecipe(recipe=r2, order_index=1),
            ],
        )

        summary = build_meal_summary(meal)
        assert summary.component_count == 2
        assert summary.image_urls == ["https://cdn/a.jpg", None]

    def test_archived_book_drops_image(self):
        from api.v1.meal_event._meal_binding import build_meal_summary

        r = MockRecipe(id=str(uuid.uuid4()), image_url="https://cdn/a.jpg")

        class _ArchivedBook:
            archived_at = datetime.now(timezone.utc)

        r.recipe_book = _ArchivedBook()
        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[MockMealRecipe(recipe=r, order_index=0)],
        )

        summary = build_meal_summary(meal)
        assert summary.image_urls == [None]

    def test_null_recipe_relationship_drops_image(self):
        from api.v1.meal_event._meal_binding import build_meal_summary

        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[MockMealRecipe(recipe=None, order_index=0)],
        )

        summary = build_meal_summary(meal)
        assert summary.image_urls == [None]

    def test_caps_image_urls_at_four(self):
        from api.v1.meal_event._meal_binding import build_meal_summary

        components = []
        for idx in range(6):
            r = MockRecipe(id=str(uuid.uuid4()), image_url=f"https://cdn/{idx}.jpg")
            r.recipe_book = None
            components.append(MockMealRecipe(recipe=r, order_index=idx))

        meal = MockMeal(id=str(uuid.uuid4()), components=components)

        summary = build_meal_summary(meal)
        assert summary.component_count == 6
        assert len(summary.image_urls) == 4
