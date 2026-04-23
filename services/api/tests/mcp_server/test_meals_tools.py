"""Tests for MCP meal tools (msa-3).

The seven tools wrap foundation Endpoints via `call_endpoint_async`; two of
them add confirmation-gate branches:

* `remove_recipe_from_meal` returns `CONFIRMATION_REQUIRED` when the
  target Meal has exactly 2 components.
* `archive_meal` returns `CONFIRMATION_REQUIRED` when the Meal has
  live references (upcoming events / active recurrence rules) and the
  caller didn't pass `confirmed=True`.

aam-10: tools are `async def`; tests await them. Confirmation-gate
reads go through `await db.execute(select(...))` on the async
database — stubbed with `AsyncMock` + `MockExecuteResult`-style
shims.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    from mcp_server.auth import (
        current_database,
        current_database_async,
        current_user,
    )

    user = MagicMock()
    sync_database = MagicMock()
    async_database = MagicMock()
    async_database.db = MagicMock()
    utok = current_user.set(user)
    dtok = current_database.set(sync_database)
    adtok = current_database_async.set(async_database)
    try:
        yield user, async_database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)
        current_database_async.reset(adtok)


def _scalar_one_result(value):
    """Stub for `await db.execute(...)` returning a scalar_one()-able."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _scalars_all_result(items):
    """Stub for `await db.execute(...)` with `.scalars().all()` chain."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = list(items)
    result.scalars.return_value = scalars
    return result


def _scalars_first_result(item):
    """Stub for `await db.execute(...)` with `.scalars().first()` chain."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = item
    result.scalars.return_value = scalars
    return result


class TestCreateMeal:
    async def test_forwards_params_to_create_endpoint(self, mcp_context):
        from mcp_server.tools.meals import create_meal

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await create_meal("book-1", "Summer Lunch", ["r1", "r2"], description="x")
        call = mock_call.call_args
        assert call.kwargs["book_id"] == "book-1"
        params = call.kwargs["params"]
        assert params.name == "Summer Lunch"
        assert params.component_recipe_ids == ["r1", "r2"]
        assert params.description == "x"

    async def test_rejects_fewer_than_two_components(self, mcp_context):
        from mcp_server.tools.meals import create_meal

        with pytest.raises(ValueError):
            await create_meal("book-1", "X", ["r1"])


class TestGetMeal:
    async def test_forwards_meal_id(self, mcp_context):
        from mcp_server.tools.meals import get_meal

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await get_meal("meal-1")
        assert mock_call.call_args.kwargs == {"meal_id": "meal-1"}


class TestListMeals:
    async def test_no_filter_passes_through(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = json.dumps(
                {"items": [{"name": "A"}, {"name": "B"}], "total": 2}
            )
            raw = await list_meals(limit=5, offset=0)
        kwargs = mock_call.call_args.kwargs
        assert kwargs == {"limit": 5, "offset": 0}
        assert json.loads(raw)["total"] == 2

    async def test_q_filter_applies_client_side_on_name(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        payload = {
            "items": [
                {"name": "Lemon Dressing", "description": None},
                {"name": "Kale Salad", "description": "Crunchy"},
            ],
            "total": 2,
        }
        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = json.dumps(payload)
            raw = await list_meals(q="lemon")
        out = json.loads(raw)
        assert out["total"] == 1
        assert out["items"][0]["name"] == "Lemon Dressing"

    async def test_q_filter_applies_to_description(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        payload = {
            "items": [
                {"name": "Lemon Dressing", "description": None},
                {"name": "Kale Salad", "description": "Crunchy"},
            ],
            "total": 2,
        }
        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = json.dumps(payload)
            raw = await list_meals(q="crunchy")
        out = json.loads(raw)
        assert out["total"] == 1
        assert out["items"][0]["name"] == "Kale Salad"

    async def test_q_whitespace_only_is_passthrough(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        payload = {"items": [{"name": "A"}], "total": 1}
        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = json.dumps(payload)
            raw = await list_meals(q="   ")
        # Whitespace-only q is treated as no filter — payload unchanged.
        assert json.loads(raw) == payload

    async def test_non_json_endpoint_response_returned_as_is(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "Error: boom"
            raw = await list_meals(q="anything")
        assert raw == "Error: boom"

    async def test_non_dict_payload_returned_as_is(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = json.dumps(["not", "a", "dict"])
            raw = await list_meals(q="x")
        assert raw == json.dumps(["not", "a", "dict"])

    async def test_items_not_a_list_returned_as_is(self, mcp_context):
        from mcp_server.tools.meals import list_meals

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = json.dumps({"items": "oops", "total": 0})
            raw = await list_meals(q="x")
        assert json.loads(raw)["items"] == "oops"


class TestUpdateMeal:
    async def test_forwards_name_and_description(self, mcp_context):
        from mcp_server.tools.meals import update_meal

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await update_meal("meal-1", name="Picnic Box", description="portable")
        params = mock_call.call_args.kwargs["params"]
        assert params.name == "Picnic Box"
        assert params.description == "portable"

    async def test_allows_nulling_fields(self, mcp_context):
        from mcp_server.tools.meals import update_meal

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await update_meal("meal-1")
        params = mock_call.call_args.kwargs["params"]
        assert params.name is None
        assert params.description is None


class TestAddRecipeToMeal:
    async def test_forwards_recipe_and_order(self, mcp_context):
        from mcp_server.tools.meals import add_recipe_to_meal

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await add_recipe_to_meal("meal-1", "r-new", order_index=2)
        call = mock_call.call_args
        assert call.kwargs["meal_id"] == "meal-1"
        assert call.kwargs["params"].recipe_id == "r-new"
        assert call.kwargs["params"].order_index == 2


class TestRemoveRecipeFromMeal:
    async def test_silent_remove_above_two_components(self, mcp_context):
        from mcp_server.tools.meals import remove_recipe_from_meal

        _, database = mcp_context
        # The tool runs `await db.execute(select(func.count())...)` →
        # `.scalar_one()` — return 3 components so the gate passes.
        database.db.execute = AsyncMock(return_value=_scalar_one_result(3))

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            result = await remove_recipe_from_meal("meal-1", "r1")
        mock_call.assert_called_once()
        assert mock_call.call_args.kwargs == {
            "meal_id": "meal-1",
            "recipe_id": "r1",
        }
        assert result == "{}"

    async def test_degenerate_two_components_returns_confirmation_required(
        self, mcp_context
    ):
        from mcp_server.tools.meals import remove_recipe_from_meal

        _, database = mcp_context
        database.db.execute = AsyncMock(return_value=_scalar_one_result(2))

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            result = await remove_recipe_from_meal("meal-1", "r1")
        # Endpoint NOT called — the gate short-circuits.
        mock_call.assert_not_called()
        payload = json.loads(result)
        assert payload["success"] is False
        assert payload["error"] == "CONFIRMATION_REQUIRED"
        assert "only 1 component" in payload["reason"]


class TestArchiveMeal:
    def _setup_no_live_refs(self, database):
        """Configure the DB mock to report zero references."""
        database.db.execute = AsyncMock(
            side_effect=[
                _scalars_all_result([]),  # events
                _scalars_all_result([]),  # rules
            ]
        )

    def _setup_with_events(
        self, database, meal_name="Summer Lunch", events=None, rules=None
    ):
        """Side-effect the three sequential .execute() calls: events, rules, meal."""
        meal = MagicMock()
        meal.name = meal_name
        meal.id = "meal-1"
        database.db.execute = AsyncMock(
            side_effect=[
                _scalars_all_result(events or []),
                _scalars_all_result(rules or []),
                _scalars_first_result(meal),
            ]
        )

    async def test_confirmed_true_bypasses_reference_check(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        # Even with live references, confirmed=True skips the check.
        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            result = await archive_meal("meal-1", confirmed=True)
        mock_call.assert_called_once_with(
            mock_call.call_args.args[0], meal_id="meal-1"
        )
        assert result == "{}"

    async def test_zero_references_archives_silently(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        self._setup_no_live_refs(database)

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            result = await archive_meal("meal-1")
        mock_call.assert_called_once()
        assert result == "{}"

    async def test_live_events_block_without_confirmed(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        future = datetime.now(UTC) + timedelta(days=1)
        ev = MagicMock()
        ev.id = "ev-1"
        ev.title = "Monday Dinner"
        ev.scheduled_at = future
        ev.meal_type = "dinner"
        self._setup_with_events(database, events=[ev])

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            result = await archive_meal("meal-1")
        mock_call.assert_not_called()
        payload = json.loads(result)
        assert payload["error"] == "CONFIRMATION_REQUIRED"
        assert "upcoming event" in payload["reason"]
        assert len(payload["events"]) == 1
        assert payload["events"][0]["title"] == "Monday Dinner"

    async def test_live_rules_block_without_confirmed(self, mcp_context):
        from mcp_server.tools.meals import archive_meal

        _, database = mcp_context
        rule = MagicMock()
        rule.id = "rule-1"
        rule.rrule = "FREQ=WEEKLY;BYDAY=MO"
        rule.meal_type = "dinner"
        self._setup_with_events(database, rules=[rule])

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            result = await archive_meal("meal-1")
        mock_call.assert_not_called()
        payload = json.loads(result)
        assert payload["error"] == "CONFIRMATION_REQUIRED"
        assert len(payload["rules"]) == 1

    async def test_live_refs_without_meal_lookup_still_returns_gate(self, mcp_context):
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
        database.db.execute = AsyncMock(
            side_effect=[
                _scalars_all_result([ev]),
                _scalars_all_result([]),
                _scalars_first_result(None),  # no Meal row
            ]
        )

        with patch(
            "mcp_server.tools.meals.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            result = await archive_meal("meal-1")
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
