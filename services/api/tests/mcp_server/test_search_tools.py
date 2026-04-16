"""Tests for MCP search tools (MCP.6)."""

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


class TestUnifiedSearch:
    def test_bare_call_only_q(self, mcp_context):
        from mcp_server.tools.search import unified_search

        with patch("mcp_server.tools.search.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            unified_search(q="pasta")
        assert mock_call.call_args.kwargs == {"q": "pasta", "limit": 20}

    def test_with_all_filters(self, mcp_context):
        from mcp_server.tools.search import unified_search

        with patch("mcp_server.tools.search.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            unified_search(
                q="curry",
                limit=5,
                book_id="b1",
                tags="spicy,quick",
                max_prep_time=10,
                max_cook_time=30,
            )
        kwargs = mock_call.call_args.kwargs
        assert kwargs["q"] == "curry"
        assert kwargs["book_id"] == "b1"
        assert kwargs["tags"] == "spicy,quick"
        assert kwargs["max_prep_time"] == 10
        assert kwargs["max_cook_time"] == 30


class TestSearchIngredients:
    def test_default_limit(self, mcp_context):
        from mcp_server.tools.search import search_ingredients

        with patch("mcp_server.tools.search.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            search_ingredients(q="tomato")
        assert mock_call.call_args.kwargs == {"q": "tomato", "limit": 10}

    def test_explicit_limit(self, mcp_context):
        from mcp_server.tools.search import search_ingredients

        with patch("mcp_server.tools.search.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            search_ingredients(q="basil", limit=5)
        assert mock_call.call_args.kwargs["limit"] == 5


class TestRegistration:
    def test_search_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        assert {"unified_search", "search_ingredients"}.issubset(names)
