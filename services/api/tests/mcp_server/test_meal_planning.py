"""Tests for MCP meal planning tools (MCP.5)."""

from datetime import date, datetime
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


class TestListMealEvents:
    def test_bare_call(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with patch("mcp_server.tools.meal_planning.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            list_meal_events()
        kwargs = mock_call.call_args.kwargs
        assert kwargs == {"limit": 20, "offset": 0}

    def test_all_filters(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with patch("mcp_server.tools.meal_planning.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            list_meal_events(
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

    def test_bad_start_date(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with pytest.raises(ValueError, match="start_date"):
            list_meal_events(start_date="not-a-date")

    def test_bad_end_date(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with pytest.raises(ValueError, match="end_date"):
            list_meal_events(end_date="also-not")

    def test_bad_meal_type(self, mcp_context):
        from mcp_server.tools.meal_planning import list_meal_events

        with pytest.raises(ValueError, match="meal_type"):
            list_meal_events(meal_type="brinner")


class TestCreateMealEvent:
    def test_creates_with_recipe(self, mcp_context):
        from mcp_server.tools.meal_planning import create_meal_event

        with patch("mcp_server.tools.meal_planning.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            create_meal_event(
                title="Pasta Night",
                scheduled_at="2026-05-01T18:30:00",
                meal_type="dinner",
                recipe_id="r1",
                description="family dinner",
            )
        params = mock_call.call_args.kwargs["params"]
        assert params.title == "Pasta Night"
        assert params.scheduled_at == datetime(2026, 5, 1, 18, 30)
        assert params.meal_type == "dinner"
        assert params.recipe_id == "r1"
        assert params.description == "family dinner"

    def test_bad_meal_type(self, mcp_context):
        from mcp_server.tools.meal_planning import create_meal_event

        with pytest.raises(ValueError, match="meal_type"):
            create_meal_event(
                title="x", scheduled_at="2026-05-01T18:00:00", meal_type="brinner"
            )

    def test_bad_datetime(self, mcp_context):
        from mcp_server.tools.meal_planning import create_meal_event

        with pytest.raises(ValueError, match="scheduled_at"):
            create_meal_event(
                title="x", scheduled_at="tomorrow", meal_type="dinner"
            )


class TestGetMealEvent:
    def test_delegates(self, mcp_context):
        from mcp_server.tools.meal_planning import get_meal_event

        with patch("mcp_server.tools.meal_planning.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            get_meal_event("e1")
        assert mock_call.call_args.kwargs == {"event_id": "e1"}


class TestRegistration:
    def test_meal_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        assert {"list_meal_events", "create_meal_event", "get_meal_event"}.issubset(
            names
        )
