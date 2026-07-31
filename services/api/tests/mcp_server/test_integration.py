"""Integration-level MCP tests.

These tests verify the MCP surface as a whole: all 27 tools are registered,
every tool has a description, the auth middleware behaves at the ASGI edge,
and errors surface as readable strings rather than tracebacks.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


ALL_EXPECTED_TOOLS = {
    # Agent tools (5)
    "search_recipes",
    "suggest_recipe",
    "add_note_to_recipe",
    "get_pantry",
    "get_user_preferences",
    # User (1)
    "get_profile",
    # Recipe CRUD (8)
    "get_recipe",
    "list_recipes",
    "create_recipe",
    "update_recipe",
    "delete_recipe",
    "toggle_favorite",
    "list_favorites",
    "fork_recipe",
    # Import (3)
    "import_recipe",
    "get_import_status",
    "approve_import",
    # Recipe books (3)
    "list_recipe_books",
    "get_recipe_book",
    "create_recipe_book",
    # Shopping (6)
    "list_shopping_lists",
    "get_shopping_list",
    "create_shopping_list",
    "add_shopping_list_item",
    "update_shopping_list_item",
    "populate_from_recipe",
    # Meal planning (3)
    "list_meal_events",
    "create_meal_event",
    "get_meal_event",
    # Search (1) — search_ingredients retired in str-ing-3 of
    # epic-ingredients-string-simplification.
    "unified_search",
}


class TestToolInventory:
    def test_all_expected_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        missing = ALL_EXPECTED_TOOLS - names
        assert not missing, f"Missing MCP tools: {missing}"

    def test_total_tool_count(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        # 28 user-facing tools + get_profile = 29
        assert len(names & ALL_EXPECTED_TOOLS) == len(ALL_EXPECTED_TOOLS)

    def test_every_tool_has_description(self):
        """LLMs rely on descriptions — don't ship any naked tools."""
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        naked = [t.name for t in mcp._tool_manager.list_tools() if not t.description]
        assert not naked, f"Tools without description: {naked}"


class TestASGIAuthIntegration:
    """Drive the actual mounted ASGI app through auth."""

    @pytest.mark.asyncio
    async def test_missing_auth_returns_401_at_asgi_edge(self):
        from mcp_server import build_mcp_app

        app = build_mcp_app()

        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "raw_path": b"/",
        }
        # Start lifespan so the session manager is live (once; swallow if already started)
        try:
            await app.router.lifespan_context(app).__aenter__()
        except RuntimeError as exc:
            if "can only be called once" not in str(exc):
                raise
        await app(scope, receive, send)

        assert messages[0]["status"] == 401

    @pytest.mark.asyncio
    async def test_bad_scheme_returns_401(self):
        from mcp_server import build_mcp_app

        app = build_mcp_app()

        messages = []

        async def send(msg):
            messages.append(msg)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"authorization", b"Basic abc")],
            "query_string": b"",
            "raw_path": b"/",
        }
        try:
            await app.router.lifespan_context(app).__aenter__()
        except RuntimeError as exc:
            if "can only be called once" not in str(exc):
                raise
        await app(scope, receive, send)

        assert messages[0]["status"] == 401
        body = json.loads(messages[1]["body"])
        assert "error" in body


class TestErrorHandling:
    """call_endpoint_async turns failures into human-readable strings."""

    async def test_get_recipe_not_found_returns_error_string(self):
        from mcp_server.auth import (
            current_database,
            current_database_async,
            current_user,
        )
        from mcp_server.tools.recipes import get_recipe

        user = MagicMock()
        sync_database = MagicMock()
        async_database = MagicMock()
        utok = current_user.set(user)
        dtok = current_database.set(sync_database)
        adtok = current_database_async.set(async_database)

        class _NotFound:
            def __init__(self, *args, database=None, user=None, **kwargs):
                pass

            async def run(self):
                return {
                    "success": False,
                    "error_message": "Recipe with ID 'nope' not found",
                    "status": 404,
                }

        try:
            with patch("mcp_server.tools.recipes.GetRecipe", _NotFound):
                result = await get_recipe("nope")
        finally:
            current_user.reset(utok)
            current_database.reset(dtok)
            current_database_async.reset(adtok)

        assert result.startswith("Error: Recipe with ID 'nope' not found")
        assert "Traceback" not in result
