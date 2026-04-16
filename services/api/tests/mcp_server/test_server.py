"""Tests for call_endpoint, call_agent_tool, and mount wiring."""

import json
from unittest.mock import MagicMock

import pytest


class _FakeEndpoint:
    """Minimal Endpoint-like class usable without going through Endpoint.run()."""

    def __init__(self, database=None, user=None):
        self.database = database
        self.user = user

    def run(self, *args, **kwargs):
        return {
            "success": True,
            "data": {"seen_user": str(self.user.id), "args": list(args), "kwargs": kwargs},
            "status": 200,
        }


class _FailingEndpoint:
    def __init__(self, database=None, user=None):
        pass

    def run(self, *args, **kwargs):
        return {
            "success": False,
            "error_message": "boom",
            "status": 500,
        }


class _RaisingEndpoint:
    def __init__(self, database=None, user=None):
        pass

    def run(self, *args, **kwargs):
        raise RuntimeError("oops")


class TestCallEndpoint:
    def test_success_returns_json_string(self):
        from mcp_server.auth import current_database, current_user
        from mcp_server.server import call_endpoint

        user = MagicMock()
        user.id = "u1"
        database = MagicMock()
        utok = current_user.set(user)
        dtok = current_database.set(database)
        try:
            result = call_endpoint(_FakeEndpoint, "pos", foo="bar")
        finally:
            current_user.reset(utok)
            current_database.reset(dtok)

        parsed = json.loads(result)
        assert parsed["seen_user"] == "u1"
        assert parsed["args"] == ["pos"]
        assert parsed["kwargs"] == {"foo": "bar"}

    def test_failure_returns_error_message(self):
        from mcp_server.auth import current_database, current_user
        from mcp_server.server import call_endpoint

        utok = current_user.set(MagicMock(id="u"))
        dtok = current_database.set(MagicMock())
        try:
            result = call_endpoint(_FailingEndpoint)
        finally:
            current_user.reset(utok)
            current_database.reset(dtok)

        assert result.startswith("Error: boom")

    def test_exception_returns_error_message(self):
        from mcp_server.auth import current_database, current_user
        from mcp_server.server import call_endpoint

        utok = current_user.set(MagicMock(id="u"))
        dtok = current_database.set(MagicMock())
        try:
            result = call_endpoint(_RaisingEndpoint)
        finally:
            current_user.reset(utok)
            current_database.reset(dtok)

        assert result.startswith("Error:")

    def test_missing_user_raises(self):
        from mcp_server.server import call_endpoint

        with pytest.raises(Exception):
            call_endpoint(_FakeEndpoint)


class _FakeAgentTool:
    name = "fake_tool"

    def execute(self, db, user_id, **kwargs):
        from agent.tools.base import ToolResult

        return ToolResult(success=True, data={"db_given": db is not None, "user_id": user_id, **kwargs})


class _FailingAgentTool:
    name = "failing_tool"

    def execute(self, db, user_id, **kwargs):
        raise RuntimeError("tool crash")


class TestCallAgentTool:
    @pytest.mark.asyncio
    async def test_runs_on_worker_thread_with_context(self):
        from mcp_server.auth import current_database, current_user
        from mcp_server.server import call_agent_tool

        user = MagicMock()
        user.id = "user-xyz"
        database = MagicMock()
        database.db = MagicMock()

        utok = current_user.set(user)
        dtok = current_database.set(database)
        try:
            result = await call_agent_tool(_FakeAgentTool(), foo="bar")
        finally:
            current_user.reset(utok)
            current_database.reset(dtok)

        parsed = json.loads(result)
        assert parsed["db_given"] is True
        assert parsed["user_id"] == "user-xyz"
        assert parsed["foo"] == "bar"

    @pytest.mark.asyncio
    async def test_exception_is_converted_to_error_string(self):
        from mcp_server.auth import current_database, current_user
        from mcp_server.server import call_agent_tool

        utok = current_user.set(MagicMock(id="u"))
        dtok = current_database.set(MagicMock(db=MagicMock()))
        try:
            result = await call_agent_tool(_FailingAgentTool())
        finally:
            current_user.reset(utok)
            current_database.reset(dtok)

        assert result.startswith("Error:")


class TestMCPAppMount:
    def test_main_app_mounts_mcp_at_prefix(self):
        from main import app

        mcp_mounts = [r for r in app.routes if getattr(r, "path", "") == "/mcp"]
        assert len(mcp_mounts) == 1, "expected exactly one /mcp mount on FastAPI app"

    def test_build_mcp_app_registers_tools(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        tool_names = {tool.name for tool in mcp._tool_manager.list_tools()}
        assert "get_profile" in tool_names


class TestGetProfileTool:
    def test_returns_expected_fields(self):
        from mcp_server.auth import current_user
        from mcp_server.tools.user import get_profile

        user = MagicMock()
        user.id = "u1"
        user.name = "Jane"
        user.email = "jane@example.com"
        user.username = "jane"
        user.has_completed_onboarding = True
        user.default_recipe_book_id = "book-1"
        user.default_shopping_list_id = None

        tok = current_user.set(user)
        try:
            raw = get_profile()
        finally:
            current_user.reset(tok)

        parsed = json.loads(raw)
        assert parsed["name"] == "Jane"
        assert parsed["email"] == "jane@example.com"
        assert parsed["default_recipe_book_id"] == "book-1"
        assert parsed["default_shopping_list_id"] is None
