"""mcal-3 tests — recurrence_rule endpoints accept `meal_id` XOR `recipe_id`.

Mirrors `test_meal_event_with_meals.py` structure — the recurrence-rule
surface gets the same XOR validator, meal access check, and meal_summary
hydration chain.
"""

import uuid
from datetime import date, datetime, timezone

from conftest import (
    MockModel,
    MockQuery,
    MockRecipe,
    MockRecipeBookUser,
)

from test_recurrence_rule import MockMealRecurrenceRule


class MockMeal(MockModel):
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
    def __init__(self, **kwargs):
        defaults = {
            "meal_id": str(uuid.uuid4()),
            "recipe_id": str(uuid.uuid4()),
            "order_index": 0,
            "recipe": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _make_meal_with_components(*, archived=False):
    from utils.models.meal import Meal as MealModel

    book_id = str(uuid.uuid4())
    r_a = MockRecipe(id=str(uuid.uuid4()), name="Kale Salad", image_url="https://cdn/a.jpg", recipe_book_id=book_id)
    r_a.recipe_book = None
    r_b = MockRecipe(id=str(uuid.uuid4()), name="Lemon Dressing", image_url="https://cdn/b.jpg", recipe_book_id=book_id)
    r_b.recipe_book = None
    meal = MockMeal(
        id=str(uuid.uuid4()),
        name="Kale Salad Meal",
        recipe_book_id=book_id,
        components=[
            MockMealRecipe(recipe=r_a, order_index=0),
            MockMealRecipe(recipe=r_b, order_index=1),
        ],
    )
    if archived:
        meal.archived_at = datetime.now(timezone.utc)
    return meal, book_id, MealModel


def _valid_body(**overrides):
    body = {
        "calendar_id": str(uuid.uuid4()),
        "meal_type": "dinner",
        "weekdays": ["mon"],
        "interval": "weekly",
        "start_date": date.today().isoformat(),
        "tz_name": "America/Los_Angeles",
        "is_shared": False,
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# XOR rejection
# ---------------------------------------------------------------------------


class TestRecurrenceXor:
    def test_create_rejects_both_recipe_id_and_meal_id(self, client, mock_db, mock_user):
        body = _valid_body(
            recipe_id=str(uuid.uuid4()), meal_id=str(uuid.uuid4())
        )
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 422
        assert response.json()["error_code"] == 135


# ---------------------------------------------------------------------------
# Create in Meal mode
# ---------------------------------------------------------------------------


class TestRecurrenceCreateMealMode:
    def test_create_rule_with_meal_id_returns_meal_summary(
        self, client, mock_db, mock_user
    ):
        from utils.models.recipe_book_user import RecipeBookUser

        meal, book_id, MealModel = _make_meal_with_components()
        # MealService loads Meal then RecipeBookUser via db.query;
        # materializer also queries MealEvent. Route by model to
        # avoid returning a Meal row to the materializer's MealEvent query.
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )

        def _query_router(model):
            if model is MealModel:
                return MockQuery([meal])
            if model is RecipeBookUser:
                return MockQuery([membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _query_router
        mock_db.set_find_by(
            RecipeBookUser, membership,
            user_id=mock_user.id, recipe_book_id=book_id,
        )

        body = _valid_body(meal_id=str(meal.id))
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["meal_id"] == str(meal.id)
        assert data["meal_summary"]["name"] == "Kale Salad Meal"
        # Title stored as None since the rule derives display title from the Meal.
        assert data["title"] is None

    def test_create_meal_rule_404_on_missing_meal(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])  # no meal found
        body = _valid_body(meal_id=str(uuid.uuid4()))
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 404

    def test_create_meal_rule_404_on_archived_meal(self, client, mock_db, mock_user):
        from utils.models.recipe_book_user import RecipeBookUser

        meal, book_id, MealModel = _make_meal_with_components(archived=True)

        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )

        def _query_router(model):
            if model is MealModel:
                return MockQuery([meal])
            if model is RecipeBookUser:
                return MockQuery([membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _query_router
        mock_db.set_find_by(
            RecipeBookUser, membership,
            user_id=mock_user.id, recipe_book_id=book_id,
        )
        body = _valid_body(meal_id=str(meal.id))
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 404

    def test_create_rule_accepts_meal_id_without_title(
        self, client, mock_db, mock_user
    ):
        """Previously title was required when recipe_id was unset — meal_id
        now satisfies the same constraint."""
        from utils.models.recipe_book_user import RecipeBookUser

        meal, book_id, MealModel = _make_meal_with_components()

        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )

        def _query_router(model):
            if model is MealModel:
                return MockQuery([meal])
            if model is RecipeBookUser:
                return MockQuery([membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _query_router
        mock_db.set_find_by(
            RecipeBookUser, membership,
            user_id=mock_user.id, recipe_book_id=book_id,
        )
        body = _valid_body(meal_id=str(meal.id))
        assert "title" not in body
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# Regression: recipe-only + free-text paths unchanged
# ---------------------------------------------------------------------------


class TestRecurrenceRegression:
    def test_create_freetext_rule_still_works(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        body = _valid_body(title="Takeout Mondays")
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["meal_id"] is None
        assert data["meal_summary"] is None

    def test_create_recipe_rule_still_works(self, client, mock_db, mock_user):
        from utils.models.recipe import Recipe

        recipe = MockRecipe(id=str(uuid.uuid4()), name="Pizza")
        mock_db.set_find_by(Recipe, recipe, id=recipe.id)
        mock_db.db.query.return_value = MockQuery([])

        body = _valid_body(recipe_id=recipe.id)
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["meal_id"] is None
        assert data["meal_summary"] is None


# ---------------------------------------------------------------------------
# Get / list hydration
# ---------------------------------------------------------------------------


class TestRecurrenceUpdateMealMode:
    def test_scope_all_switch_recipe_rule_to_meal_mode(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.recipe_book_user import RecipeBookUser

        meal, book_id, MealModel = _make_meal_with_components()
        rule_id = str(uuid.uuid4())
        existing_rule = MockMealRecurrenceRule(
            id=rule_id,
            owner_id=mock_user.id,
            calendar_id=str(uuid.uuid4()),
            recipe_id=str(uuid.uuid4()),
            meal_id=None,
            title=None,
        )
        mock_db.set_find_by(MealRecurrenceRule, existing_rule, id=rule_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )

        def _query_router(model):
            if model is MealModel:
                return MockQuery([meal])
            if model is RecipeBookUser:
                return MockQuery([membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _query_router
        mock_db.set_find_by(
            RecipeBookUser, membership,
            user_id=mock_user.id, recipe_book_id=book_id,
        )

        response = client.put(
            f"/v1/recurrence-rules/{rule_id}",
            json={"scope": "all", "meal_id": str(meal.id)},
        )
        assert response.status_code == 200
        rule = response.json()["rule"]
        assert rule["meal_id"] == str(meal.id)
        assert rule["recipe_id"] is None
        assert rule["meal_summary"]["name"] == "Kale Salad Meal"

    def test_scope_split_with_meal_id_creates_new_meal_rule(
        self, client, mock_db, mock_user
    ):
        from datetime import date, timedelta
        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.recipe_book_user import RecipeBookUser

        meal, book_id, MealModel = _make_meal_with_components()
        rule_id = str(uuid.uuid4())
        # Start date well in the past so _date_is_on_rule resolves cleanly
        # on a Monday (matches the rule weekdays=["mon"]).
        start = date.today() - timedelta(days=28)
        # Find the next Monday on/after today for the split date.
        today = date.today()
        days_to_mon = (7 - today.weekday()) % 7 or 7
        split = today + timedelta(days=days_to_mon)

        existing_rule = MockMealRecurrenceRule(
            id=rule_id,
            owner_id=mock_user.id,
            calendar_id=str(uuid.uuid4()),
            recipe_id=str(uuid.uuid4()),
            meal_id=None,
            title=None,
            start_date=start,
            weekdays=["mon"],
            interval="weekly",
            monthly_nth=None,
            tz_name="America/Los_Angeles",
            end_date=None,
        )
        mock_db.set_find_by(MealRecurrenceRule, existing_rule, id=rule_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )

        def _query_router(model):
            if model is MealModel:
                return MockQuery([meal])
            if model is RecipeBookUser:
                return MockQuery([membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _query_router
        mock_db.set_find_by(
            RecipeBookUser, membership,
            user_id=mock_user.id, recipe_book_id=book_id,
        )

        response = client.put(
            f"/v1/recurrence-rules/{rule_id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": split.isoformat(),
                "meal_id": str(meal.id),
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["new_rule"]["meal_id"] == str(meal.id)
        assert body["new_rule"]["meal_summary"]["name"] == "Kale Salad Meal"


class TestRecurrenceReads:
    def test_get_rule_with_meal_id_hydrates_summary(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        meal, book_id, MealModel = _make_meal_with_components()
        rule_id = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(
            id=rule_id, meal_id=str(meal.id), recipe_id=None, title=None,
            owner_id=mock_user.id, calendar_id=str(uuid.uuid4()),
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=rule_id)
        mock_db.db.query.return_value = MockQuery([meal])

        response = client.get(f"/v1/recurrence-rules/{rule_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["meal_id"] == str(meal.id)
        assert data["meal_summary"]["component_count"] == 2

    def test_list_rules_mixes_recipe_and_meal_items(self, client, mock_db, mock_user):
        meal, book_id, MealModel = _make_meal_with_components()
        recipe_rule = MockMealRecurrenceRule(
            id=str(uuid.uuid4()), owner_id=mock_user.id, recipe_id=str(uuid.uuid4()),
        )
        meal_rule = MockMealRecurrenceRule(
            id=str(uuid.uuid4()), owner_id=mock_user.id, meal_id=str(meal.id),
        )
        query_calls = {"rules": [recipe_rule, meal_rule], "meals": [meal]}

        def _query_router(model):
            if model is MealModel:
                return MockQuery(query_calls["meals"])
            return MockQuery(query_calls["rules"])

        mock_db.db.query.side_effect = _query_router

        response = client.get("/v1/recurrence-rules")
        assert response.status_code == 200
        items = response.json()["items"]
        by_id = {item["id"]: item for item in items}
        assert by_id[recipe_rule.id]["meal_summary"] is None
        assert by_id[meal_rule.id]["meal_summary"]["component_count"] == 2
