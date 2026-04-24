"""Tests for MCP meal planning tools (MCP.5).

aam-14: tools are `async def` + dispatch through `call_endpoint_async`.
Tests await the tool calls and patch `call_endpoint_async` with
`AsyncMock`.
"""

from datetime import date, datetime
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


class TestListMealEvents:
    async def test_bare_call(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with patch(
            "mcp_server.tools.meal_planning.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await list_meal_events()
        kwargs = mock_call.call_args.kwargs
        assert kwargs == {"limit": 20, "offset": 0}

    async def test_all_filters(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with patch(
            "mcp_server.tools.meal_planning.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await list_meal_events(
                start_date="2026-05-01",
                end_date="2026-05-07",
                meal_type="dinner",
                limit=5,
                offset=1,
            )
        kwargs = mock_call.call_args.kwargs
        assert kwargs["start_date"] == date(2026, 5, 1)
        assert kwargs["end_date"] == date(2026, 5, 7)
        assert kwargs["meal_type"] == "dinner"
        assert kwargs["limit"] == 5
        assert kwargs["offset"] == 1

    async def test_bad_start_date(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with pytest.raises(ValueError, match="start_date"):
            await list_meal_events(start_date="not-a-date")

    async def test_bad_end_date(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with pytest.raises(ValueError, match="end_date"):
            await list_meal_events(end_date="also-not")

    async def test_bad_meal_type(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with pytest.raises(ValueError, match="meal_type"):
            await list_meal_events(meal_type="brinner")


class TestCreateMealEvent:
    async def test_creates_with_recipe(self, mcp_context):
        from mcp_server.tools.meal_planning import create_meal_event

        with patch(
            "mcp_server.tools.meal_planning.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await create_meal_event(
                title="Pasta Night",
                scheduled_at="2026-05-01T18:30:00",
                meal_type="dinner",
                recipe_id="rec-1",
                description="linguine & clam sauce",
            )
        # params arrives as a CreateMealEvent.Params on the kwargs
        params = mock_call.call_args.kwargs["params"]
        assert params.title == "Pasta Night"
        assert params.scheduled_at == datetime.fromisoformat("2026-05-01T18:30:00")
        assert params.meal_type == "dinner"
        assert params.recipe_id == "rec-1"
        assert params.description == "linguine & clam sauce"

    async def test_bad_meal_type(self, mcp_context):
        from mcp_server.tools.meal_planning import create_meal_event

        with pytest.raises(ValueError, match="meal_type"):
            await create_meal_event(
                title="x",
                scheduled_at="2026-05-01T18:30:00",
                meal_type="brinner",
            )

    async def test_bad_datetime(self, mcp_context):
        from mcp_server.tools.meal_planning import create_meal_event

        with pytest.raises(ValueError, match="scheduled_at"):
            await create_meal_event(
                title="x",
                scheduled_at="not-a-datetime",
                meal_type="dinner",
            )


class TestGetMealEvent:
    async def test_delegates(self, mcp_context):
        from mcp_server.tools.meal_planning import get_meal_event

        with patch(
            "mcp_server.tools.meal_planning.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await get_meal_event(event_id="evt-123")
        assert mock_call.call_args.kwargs == {"event_id": "evt-123"}
