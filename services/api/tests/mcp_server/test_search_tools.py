"""Tests for MCP search tools (MCP.6).

aam-17: `unified_search` tool is `async def` and dispatches through
`await call_endpoint_async(...)`. Tests are async and await the tool.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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
    async def test_bare_call_only_q(self, mcp_context):
        from mcp_server.tools.search import unified_search

        with patch(
            "mcp_server.tools.search.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await unified_search(q="pasta")
        assert mock_call.call_args.kwargs == {"q": "pasta", "limit": 20}

    async def test_with_all_filters(self, mcp_context):
        from mcp_server.tools.search import unified_search

        with patch(
            "mcp_server.tools.search.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await unified_search(
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


class TestRegistration:
    def test_search_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        # search_ingredients tool was retired with
        # epic-ingredients-string-simplification (str-ing-3).
        assert "unified_search" in names
        assert "search_ingredients" not in names
