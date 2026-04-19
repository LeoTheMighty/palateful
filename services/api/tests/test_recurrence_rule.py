"""Tests for recurrence rule endpoints."""

import uuid
from datetime import date, timedelta

from conftest import MockModel, MockQuery, MockUser


class MockMealRecurrenceRule(MockModel):
    """Mock MealRecurrenceRule model."""

    def __init__(self, **kwargs):
        defaults = {
            "title": "Pizza Friday",
            "recipe_id": None,
            "meal_id": None,
            "owner_id": str(uuid.uuid4()),
            "calendar_id": str(uuid.uuid4()),
            "meal_type": "dinner",
            "weekdays": ["fri"],
            "interval": "weekly",
            "monthly_nth": None,
            "start_date": date.today(),
            "end_date": None,
            "tz_name": "America/Los_Angeles",
            "is_shared": False,
            "materialized_through": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _valid_body(**overrides):
    body = {
        "title": "Pizza Night",
        "calendar_id": str(uuid.uuid4()),
        "meal_type": "dinner",
        "weekdays": ["fri"],
        "interval": "weekly",
        "start_date": date.today().isoformat(),
        "tz_name": "America/Los_Angeles",
        "is_shared": False,
    }
    body.update(overrides)
    return body


class TestCreateRecurrenceRule:
    def test_create_freetext_rule(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])

        response = client.post("/v1/recurrence-rules", json=_valid_body())
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Pizza Night"
        assert data["interval"] == "weekly"
        assert data["weekdays"] == ["fri"]

    def test_create_rule_with_recipe(self, client, mock_db, mock_user):
        from utils.models.recipe import Recipe

        from conftest import MockRecipe

        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, name="Pizza")
        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.db.query.return_value = MockQuery([])

        body = _valid_body(recipe_id=recipe_id)
        body.pop("title")
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 201

    def test_create_rejects_missing_title_and_recipe(self, client, mock_db, mock_user):
        body = _valid_body()
        body.pop("title")
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 400

    def test_create_rejects_empty_weekdays(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(weekdays=[])
        )
        assert response.status_code == 400

    def test_create_rejects_invalid_weekday(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(weekdays=["fri", "xyz"])
        )
        assert response.status_code == 400

    def test_create_rejects_bad_interval(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(interval="yearly")
        )
        assert response.status_code == 400

    def test_create_rejects_bad_meal_type(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(meal_type="brunch")
        )
        assert response.status_code == 400

    def test_create_rejects_start_after_end(self, client, mock_db, mock_user):
        today = date.today()
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(
                start_date=today.isoformat(),
                end_date=(today - timedelta(days=1)).isoformat(),
            ),
        )
        assert response.status_code == 400

    def test_create_rejects_missing_tz(self, client, mock_db, mock_user):
        body = _valid_body()
        body["tz_name"] = ""
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 400

    def test_create_rejects_invalid_tz(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(tz_name="Mars/Olympus_Mons"),
        )
        assert response.status_code == 400

    def test_create_rejects_monthly_nth_without_monthly_interval(
        self, client, mock_db, mock_user
    ):
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(monthly_nth="first"),
        )
        assert response.status_code == 400

    def test_create_rejects_monthly_without_nth(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(interval="monthly"),
        )
        assert response.status_code == 400

    def test_create_rejects_monthly_with_multiple_weekdays(
        self, client, mock_db, mock_user
    ):
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(
                interval="monthly",
                monthly_nth="first",
                weekdays=["sat", "sun"],
            ),
        )
        assert response.status_code == 400

    def test_create_accepts_monthly(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(
                interval="monthly",
                monthly_nth="first",
                weekdays=["sat"],
            ),
        )
        assert response.status_code == 201


class TestGetRecurrenceRule:
    def test_get_own_rule(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.get(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(rule.id)

    def test_get_missing_returns_404(self, client, mock_db, mock_user):
        response = client.get(f"/v1/recurrence-rules/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_get_rule_non_calendar_member_returns_404(
        self, client, mock_db, mock_user
    ):
        """Rule on a calendar the user isn't a member of → 404 (no leak)."""
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        other_owner = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(owner_id=other_owner, is_shared=False)
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.get(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 404

    def test_get_shared_rule_via_pantry_mate(self, client, mock_db, mock_user):
        from conftest import MockPantryUser

        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.pantry_user import PantryUser

        mate_id = str(uuid.uuid4())
        shared_pantry = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(owner_id=mate_id, is_shared=True)
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        mate_membership = MockPantryUser(
            user_id=mate_id, pantry_id=shared_pantry
        )
        my_membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=shared_pantry
        )

        call_log = {"count": 0}

        def _query(model):
            if model is PantryUser:
                call_log["count"] += 1
                if call_log["count"] == 1:
                    return MockQuery([mate_membership])
                return MockQuery([my_membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        response = client.get(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(rule.id)


class TestListRecurrenceRules:
    def test_list_empty(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/recurrence-rules")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    def test_list_returns_items(self, client, mock_db, mock_user):
        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        # db.query is called for pantry-mate lookups (empty) AND for the
        # rules themselves. Route by model class.
        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.pantry_user import PantryUser

        def _query(model):
            if model is MealRecurrenceRule:
                return MockQuery([rule])
            if model is PantryUser:
                return MockQuery([])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        response = client.get("/v1/recurrence-rules")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(rule.id)


class TestCreateRecurrenceRuleExtras:
    def test_create_rejects_unknown_recipe(self, client, mock_db, mock_user):
        body = _valid_body(recipe_id=str(uuid.uuid4()))
        body.pop("title")
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 404


class TestListRecurrenceRulesPantryMates:
    def test_list_includes_pantry_mate_shared_rules(
        self, client, mock_db, mock_user
    ):
        from conftest import MockPantryUser

        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.pantry_user import PantryUser

        shared_pantry = str(uuid.uuid4())
        mate_id = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(owner_id=mate_id, is_shared=True)

        my_membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=shared_pantry
        )
        mate_membership = MockPantryUser(
            user_id=mate_id, pantry_id=shared_pantry
        )

        call_order = {"count": 0}

        def _query(model):
            if model is PantryUser:
                call_order["count"] += 1
                if call_order["count"] == 1:
                    return MockQuery([my_membership])
                return MockQuery([mate_membership])
            if model is MealRecurrenceRule:
                return MockQuery([rule])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        response = client.get("/v1/recurrence-rules")
        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestUpdateRecurrenceRule:
    def test_update_scope_all(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "all",
                "title": "Renamed",
                "weekdays": ["mon", "wed"],
            },
        )
        assert response.status_code == 200

    def test_update_scope_invalid(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "wat"},
        )
        assert response.status_code == 400

    def test_update_not_found(self, client, mock_db, mock_user):
        response = client.put(
            f"/v1/recurrence-rules/{uuid.uuid4()}",
            json={"scope": "all"},
        )
        assert response.status_code == 404

    def test_update_rejects_non_calendar_member(
        self, client, mock_db, mock_user
    ):
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(uuid.uuid4()), is_shared=False
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "all"},
        )
        assert response.status_code == 403

    def test_update_scope_all_with_recipe_not_found(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "all", "recipe_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_update_scope_all_monthly(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "all",
                "interval": "monthly",
                "monthly_nth": "first",
                "weekdays": ["sat"],
            },
        )
        assert response.status_code == 200

    def test_update_split_missing_date(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "this_and_following"},
        )
        assert response.status_code == 400

    def test_update_split_past_date(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        past = (date.today() - timedelta(days=1)).isoformat()
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "this_and_following", "occurrence_date": past},
        )
        assert response.status_code == 400

    def test_update_split_before_start(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        future_start = date.today() + timedelta(days=30)
        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            start_date=future_start,
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        before = (date.today() + timedelta(days=1)).isoformat()
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": before,
            },
        )
        assert response.status_code == 400

    def test_update_split_after_end(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            end_date=date.today() + timedelta(days=10),
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        after = (date.today() + timedelta(days=30)).isoformat()
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": after,
            },
        )
        assert response.status_code == 400

    def test_update_split_wrong_weekday(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        # Pick a future date that is NOT a Friday.
        target = date.today() + timedelta(days=1)
        while target.weekday() == 4:  # 4 == Friday
            target += timedelta(days=1)
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
            },
        )
        assert response.status_code == 400

    def test_update_split_success(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        # Find next Friday.
        target = date.today() + timedelta(days=1)
        while target.weekday() != 4:
            target += timedelta(days=1)
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
                "title": "New title",
            },
        )
        assert response.status_code == 200

    def test_update_all_with_recipe_clears_title(
        self, client, mock_db, mock_user
    ):
        from conftest import MockRecipe

        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.recipe import Recipe

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, name="Pizza")
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "all", "recipe_id": recipe_id},
        )
        assert response.status_code == 200

    def test_update_split_with_recipe_not_found(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        # Find next Friday.
        target = date.today() + timedelta(days=1)
        while target.weekday() != 4:
            target += timedelta(days=1)
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
                "recipe_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 404

    def test_update_split_with_recipe(self, client, mock_db, mock_user):
        from conftest import MockRecipe

        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.recipe import Recipe

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, name="Pasta")
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.db.query.return_value = MockQuery([])

        target = date.today() + timedelta(days=1)
        while target.weekday() != 4:
            target += timedelta(days=1)
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
                "recipe_id": recipe_id,
            },
        )
        assert response.status_code == 200

    def test_update_split_idempotent_but_no_sibling(
        self, client, mock_db, mock_user
    ):
        """rule.end_date == split_end but no sibling exists — the regular
        bounds check (occurrence_date past end_date) takes over with 400."""
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        target = date.today() + timedelta(days=1)
        while target.weekday() != 4:
            target += timedelta(days=1)

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
            end_date=target - timedelta(days=1),
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
                "title": "Replacement",
            },
        )
        assert response.status_code == 400

    def test_update_split_monthly(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            interval="monthly",
            monthly_nth="first",
            weekdays=["sat"],
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        # Find the first Saturday of next month.
        today = date.today()
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        target = next_month
        while target.weekday() != 5:
            target += timedelta(days=1)

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
                "interval": "monthly",
                "monthly_nth": "first",
                "weekdays": ["sat"],
            },
        )
        assert response.status_code == 200

    def test_update_split_idempotent(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        # Find next Friday.
        target = date.today() + timedelta(days=1)
        while target.weekday() != 4:
            target += timedelta(days=1)

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
            end_date=target - timedelta(days=1),
        )
        existing_sibling = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            start_date=target,
        )

        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        def _query(model):
            # The idempotency check issues one extra query for the sibling.
            return MockQuery([existing_sibling])

        mock_db.db.query.side_effect = _query

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
            },
        )
        assert response.status_code == 200
        assert "new_rule" in response.json()


class TestDeleteRecurrenceRule:
    def test_delete_own_rule(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_rejects_non_calendar_member(
        self, client, mock_db, mock_user
    ):
        """Non-member → 404 (existence-leak-safe, matches GET semantics)."""
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(uuid.uuid4()), is_shared=False
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 404

    def test_delete_idempotent(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from datetime import datetime

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            archived_at=datetime.utcnow(),
        )
        # Archived rules aren't returned by find_by's default — route through
        # the direct-query fallback path.
        mock_db.db.query.return_value = MockQuery([rule])

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200

    def test_delete_missing_returns_404(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.delete(f"/v1/recurrence-rules/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_delete_scope_this_and_following(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        target = (date.today() + timedelta(days=7)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_and_following&occurrence_date={target}"
        )
        assert response.status_code == 200

    def test_delete_scope_this_and_following_missing_date(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_and_following"
        )
        assert response.status_code == 400

    def test_delete_scope_this_and_following_past_end(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            end_date=date.today() - timedelta(days=10),
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        target = (date.today() + timedelta(days=7)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_and_following&occurrence_date={target}"
        )
        assert response.status_code == 200

    def test_delete_scope_this_occurrence(self, client, mock_db, mock_user):
        from conftest import MockMealEvent

        from utils.models.meal_event import MealEvent
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        # Return an event so the detach branch executes.
        event = MockMealEvent(recurrence_rule_id=str(rule.id))

        def _query(model):
            if model is MealEvent:
                return MockQuery([event])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        target = (date.today() + timedelta(days=1)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_occurrence&occurrence_date={target}"
        )
        assert response.status_code == 200
        assert event.recurrence_rule_id is None
        assert event.archived_at is not None

    def test_delete_scope_this_occurrence_no_event(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        target = (date.today() + timedelta(days=1)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_occurrence&occurrence_date={target}"
        )
        assert response.status_code == 200

    def test_delete_scope_this_occurrence_missing_date(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_occurrence"
        )
        assert response.status_code == 400

    def test_delete_invalid_scope(self, client, mock_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.db.query.return_value = MockQuery([])

        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=wat"
        )
        assert response.status_code == 400

    def test_delete_shared_rule_by_pantry_mate(self, client, mock_db, mock_user):
        from conftest import MockPantryUser

        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.pantry_user import PantryUser

        mate_id = str(uuid.uuid4())
        shared_pantry = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(owner_id=mate_id, is_shared=True)

        mate_membership = MockPantryUser(
            user_id=mate_id, pantry_id=shared_pantry
        )
        my_membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=shared_pantry
        )

        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        call_log = {"count": 0}

        def _query(model):
            if model is PantryUser:
                call_log["count"] += 1
                # First call: mate's pantry IDs. Second: my membership lookup.
                if call_log["count"] == 1:
                    return MockQuery([mate_membership])
                return MockQuery([my_membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _query

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200

    def test_delete_rejects_non_member_on_shared_rule(
        self, client, mock_db, mock_user
    ):
        """Shared/pantry flag no longer grants access — only calendar membership does. 404 masks existence."""
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(uuid.uuid4()), is_shared=True
        )
        mock_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 404
