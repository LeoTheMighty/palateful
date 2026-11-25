"""Tests for recurrence rule endpoints (aam-30 async rewrite).

All five handlers are `AsyncEndpoint` subclasses on `get_async_database`.
Tests drive them via the sync `client` fixture (async deps are already
overridden in conftest) and configure `mock_async_db` with either
`set_find_by` (for `await database.find_by(...)` lookups) or
`db.execute.side_effect` (for `await self.db.execute(select(...))`).

Materialize is dispatched via `_run_materialize` (module-local), which
opens a fresh sync Session inside the threadpool. Tests patch the
create / update modules' `_run_materialize` so materialization doesn't
touch the DB.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from conftest import MockExecuteResult, MockModel, MockUser  # noqa: F401


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


def _patch_create_materialize():
    return patch(
        "api.v1.recurrence_rule.create_recurrence_rule._run_materialize",
        new_callable=AsyncMock,
    )


def _patch_update_materialize():
    return patch(
        "api.v1.recurrence_rule.update_recurrence_rule._run_materialize",
        new_callable=AsyncMock,
    )


class TestMaterializeSyncHelpers:
    """Direct coverage of `_materialize_sync` across create/update modules.

    The normal endpoint tests patch `_run_materialize`, which shields the
    inner sync function from the threadpool dispatch. These tests invoke
    the sync helper directly with an in-memory double for `SessionLocal`.
    """

    def test_create_materialize_sync_short_circuits_when_session_local_none(
        self,
    ):
        from api.v1.recurrence_rule import create_recurrence_rule as mod

        with patch(
            "utils.services.database.SessionLocal", None
        ):
            mod._materialize_sync("some-rule-id", date.today())

    def test_update_materialize_sync_short_circuits_when_session_local_none(
        self,
    ):
        from api.v1.recurrence_rule import update_recurrence_rule as mod

        with patch(
            "utils.services.database.SessionLocal", None
        ):
            mod._materialize_sync("some-rule-id", date.today())

    def test_create_run_materialize_dispatches_to_threadpool(self):
        """Covers the `_run_materialize` async wrapper line."""
        import asyncio

        from api.v1.recurrence_rule import create_recurrence_rule as mod

        with patch.object(
            mod, "_materialize_sync"
        ) as mock_sync:
            asyncio.run(mod._run_materialize("rid", date.today()))
        mock_sync.assert_called_once_with("rid", date.today())

    def test_update_run_materialize_dispatches_to_threadpool(self):
        import asyncio

        from api.v1.recurrence_rule import update_recurrence_rule as mod

        with patch.object(
            mod, "_materialize_sync"
        ) as mock_sync:
            asyncio.run(mod._run_materialize("rid", date.today()))
        mock_sync.assert_called_once_with("rid", date.today())

    def test_create_materialize_sync_runs_when_rule_exists(self):
        """SessionLocal → Session → rule found → materialize called → commit."""
        from unittest.mock import MagicMock

        from api.v1.recurrence_rule import create_recurrence_rule as mod

        session = MagicMock()
        rule_sentinel = MockMealRecurrenceRule()
        session.query.return_value.filter.return_value.first.return_value = (
            rule_sentinel
        )
        SessionLocalFactory = MagicMock(return_value=session)

        with patch(
            "utils.services.database.SessionLocal", SessionLocalFactory
        ), patch(
            "utils.recurrence.materializer.materialize"
        ) as mock_materialize:
            mod._materialize_sync("some-rule-id", date.today())

        mock_materialize.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_create_materialize_sync_skips_when_rule_missing(self):
        """SessionLocal → Session → rule None → no materialize, still closes."""
        from unittest.mock import MagicMock

        from api.v1.recurrence_rule import create_recurrence_rule as mod

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        SessionLocalFactory = MagicMock(return_value=session)

        with patch(
            "utils.services.database.SessionLocal", SessionLocalFactory
        ), patch(
            "utils.recurrence.materializer.materialize"
        ) as mock_materialize:
            mod._materialize_sync("missing-id", date.today())

        mock_materialize.assert_not_called()
        session.close.assert_called_once()

    def test_update_materialize_sync_runs_when_rule_exists(self):
        from unittest.mock import MagicMock

        from api.v1.recurrence_rule import update_recurrence_rule as mod

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = (
            MockMealRecurrenceRule()
        )
        SessionLocalFactory = MagicMock(return_value=session)

        with patch(
            "utils.services.database.SessionLocal", SessionLocalFactory
        ), patch(
            "utils.recurrence.materializer.materialize"
        ) as mock_materialize:
            mod._materialize_sync("some-rule-id", date.today())

        mock_materialize.assert_called_once()
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_update_materialize_sync_skips_when_rule_missing(self):
        from unittest.mock import MagicMock

        from api.v1.recurrence_rule import update_recurrence_rule as mod

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        SessionLocalFactory = MagicMock(return_value=session)

        with patch(
            "utils.services.database.SessionLocal", SessionLocalFactory
        ), patch(
            "utils.recurrence.materializer.materialize"
        ) as mock_materialize:
            mod._materialize_sync("missing-id", date.today())

        mock_materialize.assert_not_called()
        session.close.assert_called_once()


class TestCreateRecurrenceRule:
    def test_create_freetext_rule(self, client, mock_async_db, mock_user):
        with _patch_create_materialize():
            response = client.post("/v1/recurrence-rules", json=_valid_body())
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Pizza Night"
        assert data["interval"] == "weekly"
        assert data["weekdays"] == ["fri"]

    def test_create_rule_with_recipe(self, client, mock_async_db, mock_user):
        from utils.models.recipe import Recipe

        from conftest import MockRecipe

        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, name="Pizza")
        mock_async_db.set_find_by(Recipe, recipe, id=recipe_id)

        body = _valid_body(recipe_id=recipe_id)
        body.pop("title")
        with _patch_create_materialize():
            response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 201

    def test_create_rejects_missing_title_and_recipe(
        self, client, mock_async_db, mock_user
    ):
        body = _valid_body()
        body.pop("title")
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 400

    def test_create_rejects_empty_weekdays(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(weekdays=[])
        )
        assert response.status_code == 400

    def test_create_rejects_invalid_weekday(
        self, client, mock_async_db, mock_user
    ):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(weekdays=["fri", "xyz"])
        )
        assert response.status_code == 400

    def test_create_rejects_bad_interval(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(interval="yearly")
        )
        assert response.status_code == 400

    def test_create_rejects_bad_meal_type(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules", json=_valid_body(meal_type="brunch")
        )
        assert response.status_code == 400

    def test_create_rejects_start_after_end(
        self, client, mock_async_db, mock_user
    ):
        today = date.today()
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(
                start_date=today.isoformat(),
                end_date=(today - timedelta(days=1)).isoformat(),
            ),
        )
        assert response.status_code == 400

    def test_create_rejects_missing_tz(self, client, mock_async_db, mock_user):
        body = _valid_body()
        body["tz_name"] = ""
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 400

    def test_create_rejects_invalid_tz(self, client, mock_async_db, mock_user):
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(tz_name="Mars/Olympus_Mons"),
        )
        assert response.status_code == 400

    def test_create_rejects_monthly_nth_without_monthly_interval(
        self, client, mock_async_db, mock_user
    ):
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(monthly_nth="first"),
        )
        assert response.status_code == 400

    def test_create_rejects_monthly_without_nth(
        self, client, mock_async_db, mock_user
    ):
        response = client.post(
            "/v1/recurrence-rules",
            json=_valid_body(interval="monthly"),
        )
        assert response.status_code == 400

    def test_create_rejects_monthly_with_multiple_weekdays(
        self, client, mock_async_db, mock_user
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

    def test_create_rejects_missing_calendar_id(
        self, client, mock_async_db, mock_user
    ):
        body = _valid_body()
        body.pop("calendar_id")
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 400

    def test_create_accepts_monthly(self, client, mock_async_db, mock_user):
        with _patch_create_materialize():
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
    def test_get_own_rule(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.get(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(rule.id)

    def test_get_missing_returns_404(self, client, mock_async_db, mock_user):
        response = client.get(f"/v1/recurrence-rules/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_get_rule_non_calendar_member_returns_404(
        self, client, mock_async_db, mock_user
    ):
        """Rule on a calendar the user isn't a member of → 404 (no leak)."""
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        other_owner = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(owner_id=other_owner, is_shared=False)
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.get(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 404

    def test_get_shared_rule_via_pantry_mate(
        self, client, mock_async_db, mock_user
    ):
        """Pantry-mate sharing is dead code (cal-found-2 replaced it with
        calendar membership). The default CalendarUser mock returns owner,
        so a shared rule is reachable via the default calendar gate."""
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        mate_id = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(owner_id=mate_id, is_shared=True)
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.get(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(rule.id)


class TestListRecurrenceRules:
    def test_list_empty(self, client, mock_async_db, mock_user):
        # get_user_calendar_ids_async → empty; rules select → empty.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),  # calendar_ids
            MockExecuteResult(items=[]),  # rules
        ]

        response = client.get("/v1/recurrence-rules")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    def test_list_returns_items(self, client, mock_async_db, mock_user):
        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        # calendar_ids, rules (meal_id None → no meal fetch).
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[rule.calendar_id]),
            MockExecuteResult(items=[rule]),
        ]

        response = client.get("/v1/recurrence-rules")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(rule.id)

    def test_list_with_calendar_id_filter(
        self, client, mock_async_db, mock_user
    ):
        """Explicit `calendar_id` query routes through
        `require_calendar_access_async` instead of `get_user_calendar_ids_async`."""
        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        # Only one execute (rules select) since calendar_id branch uses find_by
        # (owner default returns MockCalendarUser).
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[rule]),
        ]

        response = client.get(
            f"/v1/recurrence-rules?calendar_id={rule.calendar_id}"
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestCreateRecurrenceRuleExtras:
    def test_create_rejects_unknown_recipe(
        self, client, mock_async_db, mock_user
    ):
        body = _valid_body(recipe_id=str(uuid.uuid4()))
        body.pop("title")
        response = client.post("/v1/recurrence-rules", json=body)
        assert response.status_code == 404


class TestListRecurrenceRulesPantryMates:
    def test_list_includes_pantry_mate_shared_rules(
        self, client, mock_async_db, mock_user
    ):
        """Pantry-mate membership is dead code (cal-found-2). A shared
        rule on a calendar the user belongs to is visible via the normal
        calendar-id scope."""
        rule = MockMealRecurrenceRule(
            owner_id=str(uuid.uuid4()), is_shared=True
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[rule.calendar_id]),
            MockExecuteResult(items=[rule]),
        ]

        response = client.get("/v1/recurrence-rules")
        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestUpdateRecurrenceRule:
    def test_update_scope_all(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        with _patch_update_materialize():
            response = client.put(
                f"/v1/recurrence-rules/{rule.id}",
                json={
                    "scope": "all",
                    "title": "Renamed",
                    "weekdays": ["mon", "wed"],
                },
            )
        assert response.status_code == 200

    def test_update_scope_invalid(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "wat"},
        )
        assert response.status_code == 400

    def test_update_not_found(self, client, mock_async_db, mock_user):
        response = client.put(
            f"/v1/recurrence-rules/{uuid.uuid4()}",
            json={"scope": "all"},
        )
        assert response.status_code == 404

    def test_update_rejects_non_calendar_member(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(uuid.uuid4()), is_shared=False
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "all"},
        )
        assert response.status_code == 403

    def test_update_scope_all_with_recipe_not_found(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "all", "recipe_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_update_scope_all_monthly(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        with _patch_update_materialize():
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

    def test_update_split_missing_date(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "this_and_following"},
        )
        assert response.status_code == 400

    def test_update_split_past_date(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        past = (date.today() - timedelta(days=1)).isoformat()
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={"scope": "this_and_following", "occurrence_date": past},
        )
        assert response.status_code == 400

    def test_update_split_before_start(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        future_start = date.today() + timedelta(days=30)
        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            start_date=future_start,
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        before = (date.today() + timedelta(days=1)).isoformat()
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": before,
            },
        )
        assert response.status_code == 400

    def test_update_split_after_end(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            end_date=date.today() + timedelta(days=10),
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        after = (date.today() + timedelta(days=30)).isoformat()
        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": after,
            },
        )
        assert response.status_code == 400

    def test_update_split_wrong_weekday(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

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

    def test_update_split_success(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        # Find next Friday.
        target = date.today() + timedelta(days=1)
        while target.weekday() != 4:
            target += timedelta(days=1)
        with _patch_update_materialize():
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
        self, client, mock_async_db, mock_user
    ):
        from conftest import MockRecipe

        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.recipe import Recipe

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, name="Pizza")
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.set_find_by(Recipe, recipe, id=recipe_id)

        with _patch_update_materialize():
            response = client.put(
                f"/v1/recurrence-rules/{rule.id}",
                json={"scope": "all", "recipe_id": recipe_id},
            )
        assert response.status_code == 200

    def test_update_split_with_recipe_not_found(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

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

    def test_update_split_with_recipe(self, client, mock_async_db, mock_user):
        from conftest import MockRecipe

        from utils.models.meal_recurrence_rule import MealRecurrenceRule
        from utils.models.recipe import Recipe

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            weekdays=["fri"],
        )
        recipe_id = str(uuid.uuid4())
        recipe = MockRecipe(id=recipe_id, name="Pasta")
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.set_find_by(Recipe, recipe, id=recipe_id)

        target = date.today() + timedelta(days=1)
        while target.weekday() != 4:
            target += timedelta(days=1)
        with _patch_update_materialize():
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
        self, client, mock_async_db, mock_user
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
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        # Idempotent sibling lookup → empty.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),
        ]

        response = client.put(
            f"/v1/recurrence-rules/{rule.id}",
            json={
                "scope": "this_and_following",
                "occurrence_date": target.isoformat(),
                "title": "Replacement",
            },
        )
        assert response.status_code == 400

    def test_update_split_monthly(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            interval="monthly",
            monthly_nth="first",
            weekdays=["sat"],
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        # Find the first Saturday of next month.
        today = date.today()
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        target = next_month
        while target.weekday() != 5:
            target += timedelta(days=1)

        with _patch_update_materialize():
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

    def test_update_scope_all_with_move_to_calendar(
        self, client, mock_async_db, mock_user
    ):
        """scope=all with a different calendar_id → re-checks access on
        the target and cascades future meal_events."""
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        new_calendar_id = str(uuid.uuid4())
        # Move-to-calendar branch: 1 `await self.db.execute(sa_update(...))`.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),  # bulk UPDATE result
        ]

        with _patch_update_materialize():
            response = client.put(
                f"/v1/recurrence-rules/{rule.id}",
                json={"scope": "all", "calendar_id": new_calendar_id},
            )
        assert response.status_code == 200
        assert str(rule.calendar_id) == new_calendar_id

    def test_update_split_idempotent(self, client, mock_async_db, mock_user):
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

        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        # Idempotent sibling lookup returns the existing sibling.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[existing_sibling]),
        ]

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
    def test_delete_own_rule(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        # sa_delete MealEvent — 1 execute.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),
        ]

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_rejects_non_calendar_member(
        self, client, mock_async_db, mock_user
    ):
        """Non-member → 404 (existence-leak-safe, matches GET semantics)."""
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(uuid.uuid4()), is_shared=False
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 404

    def test_delete_idempotent(self, client, mock_async_db, mock_user):
        from datetime import datetime

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            archived_at=datetime.utcnow(),
        )
        # find_by MealRecurrenceRule → None (no set_find_by).
        # Fallback execute returns the archived rule.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[rule]),
        ]

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200

    def test_delete_missing_returns_404(
        self, client, mock_async_db, mock_user
    ):
        # find_by → None; fallback execute → empty.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),
        ]
        response = client.delete(f"/v1/recurrence-rules/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_delete_scope_this_and_following(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        # sa_delete MealEvent — 1 execute.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),
        ]

        target = (date.today() + timedelta(days=7)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_and_following&occurrence_date={target}"
        )
        assert response.status_code == 200

    def test_delete_scope_this_and_following_missing_date(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_and_following"
        )
        assert response.status_code == 400

    def test_delete_scope_this_and_following_past_end(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(mock_user.id),
            end_date=date.today() - timedelta(days=10),
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        target = (date.today() + timedelta(days=7)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_and_following&occurrence_date={target}"
        )
        assert response.status_code == 200

    def test_delete_scope_this_occurrence(
        self, client, mock_async_db, mock_user
    ):
        from conftest import MockMealEvent

        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        event = MockMealEvent(recurrence_rule_id=str(rule.id))
        # Single MealEvent select.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
        ]

        target = (date.today() + timedelta(days=1)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_occurrence&occurrence_date={target}"
        )
        assert response.status_code == 200
        assert event.archived_at is not None
        # rcres1: the row stays attached to the rule so the materializer sees
        # its slot as occupied. Detaching here resurrected the occurrence on
        # the next window advance.
        assert event.recurrence_rule_id == str(rule.id)

    def test_delete_scope_this_occurrence_no_event(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),
        ]

        target = (date.today() + timedelta(days=1)).isoformat()
        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_occurrence&occurrence_date={target}"
        )
        assert response.status_code == 200

    def test_delete_scope_this_occurrence_missing_date(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=this_occurrence"
        )
        assert response.status_code == 400

    def test_delete_invalid_scope(self, client, mock_async_db, mock_user):
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(owner_id=str(mock_user.id))
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))

        response = client.delete(
            f"/v1/recurrence-rules/{rule.id}?scope=wat"
        )
        assert response.status_code == 400

    def test_delete_shared_rule_by_pantry_mate(
        self, client, mock_async_db, mock_user
    ):
        """Pantry-mate gate is dead code (cal-found-2). Calendar-owner
        default on the mock means any member can delete a shared rule."""
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        mate_id = str(uuid.uuid4())
        rule = MockMealRecurrenceRule(owner_id=mate_id, is_shared=True)
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[]),
        ]

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 200

    def test_delete_rejects_non_member_on_shared_rule(
        self, client, mock_async_db, mock_user
    ):
        """Shared flag no longer grants access — only calendar membership does. 404 masks existence."""
        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_recurrence_rule import MealRecurrenceRule

        rule = MockMealRecurrenceRule(
            owner_id=str(uuid.uuid4()), is_shared=True
        )
        mock_async_db.set_find_by(MealRecurrenceRule, rule, id=str(rule.id))
        mock_async_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=rule.calendar_id,
        )

        response = client.delete(f"/v1/recurrence-rules/{rule.id}")
        assert response.status_code == 404
