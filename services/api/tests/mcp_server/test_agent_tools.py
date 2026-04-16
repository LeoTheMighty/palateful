"""Tests for the agent-tool wrappers (MCP.2)."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    """Push a user + database into MCP contextvars for the duration of a test."""
    from mcp_server.auth import current_database, current_user

    user = MagicMock()
    user.id = "user-agent"
    database = MagicMock()
    database.db = MagicMock()

    utok = current_user.set(user)
    dtok = current_database.set(database)
    try:
        yield user, database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)


class _FakeToolResult:
    def __init__(self, data):
        self.success = True
        self.error = None
        self._data = data

    def to_message(self):
        return json.dumps(self._data)


class TestAgentToolWrappers:
    @pytest.mark.asyncio
    async def test_search_recipes_delegates_with_all_params(self, mcp_context):
        from mcp_server.tools.agent_tools import search_recipes

        fake_result = _FakeToolResult({"recipes": [], "total_found": 0, "query": "q"})

        with patch(
            "mcp_server.tools.agent_tools.SearchRecipesTool"
        ) as mock_cls:
            instance = MagicMock()
            instance.execute.return_value = fake_result
            mock_cls.return_value = instance

            raw = await search_recipes(
                query="q", max_results=3, max_cook_time=20, pantry_match=True
            )

        parsed = json.loads(raw)
        assert parsed["query"] == "q"
        kwargs = instance.execute.call_args.kwargs
        assert kwargs["query"] == "q"
        assert kwargs["max_results"] == 3
        assert kwargs["max_cook_time"] == 20
        assert kwargs["pantry_match"] is True

    @pytest.mark.asyncio
    async def test_suggest_recipe_delegates(self, mcp_context):
        from mcp_server.tools.agent_tools import suggest_recipe

        fake_result = _FakeToolResult({"suggestion": "pasta ideas"})

        with patch(
            "mcp_server.tools.agent_tools.SuggestRecipeTool"
        ) as mock_cls:
            instance = MagicMock()
            instance.execute.return_value = fake_result
            mock_cls.return_value = instance

            raw = await suggest_recipe(
                ingredients=["tomato"],
                cuisine="Italian",
                meal_type="dinner",
                dietary_restrictions=["vegetarian"],
                difficulty="easy",
            )

        parsed = json.loads(raw)
        assert parsed["suggestion"] == "pasta ideas"
        kwargs = instance.execute.call_args.kwargs
        assert kwargs["ingredients"] == ["tomato"]
        assert kwargs["cuisine"] == "Italian"
        assert kwargs["difficulty"] == "easy"

    @pytest.mark.asyncio
    async def test_add_note_to_recipe_delegates(self, mcp_context):
        from mcp_server.tools.agent_tools import add_note_to_recipe

        fake_result = _FakeToolResult(
            {"note_id": "n1", "recipe_id": "r1", "recipe_name": "Pasta"}
        )

        with patch(
            "mcp_server.tools.agent_tools.AddNoteToRecipeTool"
        ) as mock_cls:
            instance = MagicMock()
            instance.execute.return_value = fake_result
            mock_cls.return_value = instance

            raw = await add_note_to_recipe(
                note_body="Cook 5 min longer", recipe_name="Pasta"
            )

        parsed = json.loads(raw)
        assert parsed["recipe_name"] == "Pasta"
        kwargs = instance.execute.call_args.kwargs
        assert kwargs["note_body"] == "Cook 5 min longer"
        assert kwargs["recipe_name"] == "Pasta"
        assert kwargs["recipe_id"] is None

    @pytest.mark.asyncio
    async def test_get_pantry_delegates(self, mcp_context):
        from mcp_server.tools.agent_tools import get_pantry

        fake_result = _FakeToolResult({"items": [], "total_count": 0})

        with patch("mcp_server.tools.agent_tools.GetPantryTool") as mock_cls:
            instance = MagicMock()
            instance.execute.return_value = fake_result
            mock_cls.return_value = instance

            raw = await get_pantry(expiring_within_days=3, category="produce")

        parsed = json.loads(raw)
        assert parsed["total_count"] == 0
        kwargs = instance.execute.call_args.kwargs
        assert kwargs["include_expired"] is False
        assert kwargs["expiring_within_days"] == 3
        assert kwargs["category"] == "produce"

    @pytest.mark.asyncio
    async def test_get_user_preferences_delegates(self, mcp_context):
        from mcp_server.tools.agent_tools import get_user_preferences

        fake_result = _FakeToolResult(
            {"user_id": "u", "dietary_restrictions": ["vegan"]}
        )

        with patch(
            "mcp_server.tools.agent_tools.GetUserPreferencesTool"
        ) as mock_cls:
            instance = MagicMock()
            instance.execute.return_value = fake_result
            mock_cls.return_value = instance

            raw = await get_user_preferences()

        parsed = json.loads(raw)
        assert parsed["dietary_restrictions"] == ["vegan"]
        instance.execute.assert_called_once()


class TestToolRegistration:
    def test_all_five_agent_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        assert {
            "search_recipes",
            "suggest_recipe",
            "add_note_to_recipe",
            "get_pantry",
            "get_user_preferences",
        }.issubset(names)
