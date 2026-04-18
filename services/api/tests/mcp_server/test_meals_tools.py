"""Tests for MCP meal tools (msa-3).

The seven tools wrap foundation Endpoints via `call_endpoint`; two of
them add confirmation-gate branches:

* `remove_recipe_from_meal` returns `CONFIRMATION_REQUIRED` when the
  target Meal has exactly 2 components.
* `archive_meal` returns `CONFIRMATION_REQUIRED` when the Meal has
  live references (upcoming events / active recurrence rules) and the
  caller didn't pass `confirmed=True`.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    from mcp_server.auth import current_database, current_user

    user = MagicMock()
    database = MagicMock()
    utok = current_user.set(user)
    dtok = current_database.set(database)
    try:
        yield user, database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)


class _CountQuery:
    """Tiny stub used for the `db.query(MealRecipe).filter(...).count()`
    chain inside `remove_recipe_from_meal`."""

    def __init__(self, count_value: int):
        self._count = count_value

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return self._count


class _EventsQuery:
    """Stub for the full `db.query(MealEvent).filter(...).order_by(...).limit(...).all()` chain."""

    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class TestCreateMeal:
    def test_forwards_params_to_create_endpoint(self, mcp_context):
        from mcp_server.tools.meals import create_meal

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            create_meal("book-1", "Summer Lunch", ["r1", "r2"], description="x")
        call = mock_call.call_args
        assert call.kwargs["book_id"] == "book-1"
        params = call.kwargs["params"]
        assert params.name == "Summer Lunch"
        assert params.component_recipe_ids == ["r1", "r2"]
        assert params.description == "x"

    def test_rejects_fewer_than_two_components(self, mcp_context):
        from mcp_server.tools.meals import create_meal

        with pytest.raises(ValueError):
            create_meal("book-1", "X", ["r1"])


class TestGetMeal:
    def test_forwards_meal_id(self, mcp_context):
        from mcp_server.tools.meals import get_meal

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            get_meal("meal-1")
        assert mock_call.call_args.kwargs == {"meal_id": "meal-1"}


class TestListMeals:
    def test_no_filter_passes_through(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = json.dumps(
                {"items": [{"name": "A"}, {"name": "B"}], "total": 2}
            )
            raw = list_meals(limit=5, offset=0)
        kwargs = mock_call.call_args.kwargs
        assert kwargs == {"limit": 5, "offset": 0}
        assert json.loads(raw)["total"] == 2

    def test_q_filter_applies_client_side_on_name(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        payload = {
            "items": [
                {"name": "Lemon Dressing", "description": None},
                {"name": "Kale Salad", "description": "Crunchy"},
            ],
            "total": 2,
        }
        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = json.dumps(payload)
            raw = list_meals(q="lemon")
        out = json.loads(raw)
        assert out["total"] == 1
        assert out["items"][0]["name"] == "Lemon Dressing"

    def test_q_filter_applies_to_description(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        payload = {
            "items": [
                {"name": "Lemon Dressing", "description": None},
                {"name": "Kale Salad", "description": "Crunchy"},
            ],
            "total": 2,
        }
        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = json.dumps(payload)
            raw = list_meals(q="crunchy")
        out = json.loads(raw)
        assert out["total"] == 1
        assert out["items"][0]["name"] == "Kale Salad"

    def test_q_whitespace_only_is_passthrough(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        payload = {"items": [{"name": "A"}], "total": 1}
        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = json.dumps(payload)
            raw = list_meals(q="   ")
        # Whitespace-only q is treated as no filter — payload unchanged.
        assert json.loads(raw) == payload

    def test_non_json_endpoint_response_returned_as_is(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "Error: boom"
            raw = list_meals(q="anything")
        assert raw == "Error: boom"

    def test_non_dict_payload_returned_as_is(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = json.dumps(["not", "a", "dict"])
            raw = list_meals(q="x")
        assert raw == json.dumps(["not", "a", "dict"])

    def test_items_not_a_list_returned_as_is(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = json.dumps({"items": "oops", "total": 0})
            raw = list_meals(q="x")
        assert json.loads(raw)["items"] == "oops"


class TestUpdateMeal:
    def test_forwards_name_and_description(self, mcp_context):
        from mcp_server.tools.meals import update_meal

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            update_meal("meal-1", name="Picnic Box", description="portable")
        params = mock_call.call_args.kwargs["params"]
        assert params.name == "Picnic Box"
        assert params.description == "portable"

    def test_allows_nulling_fields(self, mcp_context):
        from mcp_server.tools.meals import update_meal

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            update_meal("meal-1")
        params = mock_call.call_args.kwargs["params"]
        assert params.name is None
        assert params.description is None


class TestAddRecipeToMeal:
    def test_forwards_recipe_and_order(self, mcp_context):
        from mcp_server.tools.meals import add_recipe_to_meal

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            add_recipe_to_meal("meal-1", "r-new", order_index=2)
        call = mock_call.call_args
        assert call.kwargs["meal_id"] == "meal-1"
        assert call.kwargs["params"].recipe_id == "r-new"
        assert call.kwargs["params"].order_index == 2


class TestRemoveRecipeFromMeal:
    def test_silent_remove_above_two_components(self, mcp_context):
        from mcp_server.tools.meals import remove_recipe_from_meal

        _, database = mcp_context
        database.db.query.return_value = _CountQuery(3)

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            result = remove_recipe_from_meal("meal-1", "r1")
        mock_call.assert_called_once()
        assert mock_call.call_args.kwargs == {
            "meal_id": "meal-1",
            "recipe_id": "r1",
        }
        assert result == "{}"

    def test_degenerate_two_components_returns_confirmation_required(
        self, mcp_context
    ):
        from mcp_server.tools.meals import remove_recipe_from_meal

        _, database = mcp_context
        database.db.query.return_value = _CountQuery(2)

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            result = remove_recipe_from_meal("meal-1", "r1")
        # Endpoint NOT called — the gate short-circuits.
        mock_call.assert_not_called()
        payload = json.loads(result)
        assert payload["success"] is False
        assert payload["error"] == "CONFIRMATION_REQUIRED"
        assert "only 1 component" in payload["reason"]


class TestArchiveMeal:
    def _setup_no_live_refs(self, database):
        """Configure the DB mock to report zero references."""
        database.db.query.return_value = _EventsQuery([])

    def _setup_with_events(
        self, database, meal_name="Summer Lunch", events=None, rules=None
    ):
        """Side-effect the three sequential .query() calls: events, rules, meal."""
        meal = MagicMock()
        meal.name = meal_name
        meal.id = "meal-1"
        database.db.query.side_effect = [
            _EventsQuery(events or []),
            _EventsQuery(rules or []),
            _EventsQuery([meal]),
        ]

    def test_confirmed_true_bypasses_reference_check(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        # Even with live references, confirmed=True skips the check.
        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            result = archive_meal("meal-1", confirmed=True)
        mock_call.assert_called_once_with(
            mock_call.call_args.args[0], meal_id="meal-1"
        )
        assert result == "{}"

    def test_zero_references_archives_silently(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        self._setup_no_live_refs(database)

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            result = archive_meal("meal-1")
        mock_call.assert_called_once()
        assert result == "{}"

    def test_live_events_block_without_confirmed(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        future = datetime.now(UTC) + timedelta(days=1)
        ev = MagicMock()
        ev.id = "ev-1"
        ev.title = "Monday Dinner"
        ev.scheduled_at = future
        ev.meal_type = "dinner"
        self._setup_with_events(database, events=[ev])

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            result = archive_meal("meal-1")
        mock_call.assert_not_called()
        payload = json.loads(result)
        assert payload["error"] == "CONFIRMATION_REQUIRED"
        assert "upcoming event" in payload["reason"]
        assert len(payload["events"]) == 1
        assert payload["events"][0]["title"] == "Monday Dinner"

    def test_live_rules_block_without_confirmed(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        rule = MagicMock()
        rule.id = "rule-1"
        rule.rrule = "FREQ=WEEKLY;BYDAY=MO"
        rule.meal_type = "dinner"
        self._setup_with_events(database, rules=[rule])

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            result = archive_meal("meal-1")
        mock_call.assert_not_called()
        payload = json.loads(result)
        assert payload["error"] == "CONFIRMATION_REQUIRED"
        assert len(payload["rules"]) == 1

    def test_live_refs_without_meal_lookup_still_returns_gate(self, mcp_context):
        """If the Meal row is missing (shouldn't happen in prod, but guard
        against a race) the gate still returns without including the name."""
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        future = datetime.now(UTC) + timedelta(days=1)
        ev = MagicMock()
        ev.id = "ev-1"
        ev.title = "T"
        ev.scheduled_at = future
        ev.meal_type = "dinner"
        database.db.query.side_effect = [
            _EventsQuery([ev]),
            _EventsQuery([]),
            _EventsQuery([]),  # no Meal row
        ]

        with patch("mcp_server.tools.meals.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            result = archive_meal("meal-1")
        payload = json.loads(result)
        assert payload["error"] == "CONFIRMATION_REQUIRED"
        # The reason string omits the meal name but still structured.
        assert "Meal " in payload["reason"]


class TestRegistration:
    def test_all_seven_meal_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        required = {
            "create_meal",
            "get_meal",
            "list_meals",
            "update_meal",
            "add_recipe_to_meal",
            "remove_recipe_from_meal",
            "archive_meal",
        }
        assert required.issubset(names)
