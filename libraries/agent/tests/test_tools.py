"""Tests for agent tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.tools import GetPantryTool, SearchRecipesTool, GetUserPreferencesTool
from agent.tools.base import ToolResult


class TestGetPantryTool:
    """Tests for GetPantryTool."""

    @pytest.fixture
    def tool(self):
        return GetPantryTool()

    def test_tool_properties(self, tool):
        """Test tool has correct properties."""
        assert tool.name == "get_pantry"
        assert "pantry" in tool.description.lower()
        assert "properties" in tool.parameters

    @pytest.mark.asyncio
    async def test_execute_no_pantry(self, tool):
        """Test execution when user has no pantry."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = await tool.execute(mock_db, "test-user-id")

        assert result.success
        assert result.data["items"] == []

    def test_to_langchain_tool(self, tool):
        """Test conversion to LangChain tool."""
        lc_tool = tool.to_langchain_tool()

        assert lc_tool.name == "get_pantry"
        assert lc_tool.description == tool.description


class TestSearchRecipesTool:
    """Tests for SearchRecipesTool."""

    @pytest.fixture
    def tool(self):
        return SearchRecipesTool()

    def test_tool_properties(self, tool):
        """Test tool has correct properties."""
        assert tool.name == "search_recipes"
        assert "search" in tool.description.lower()
        assert "query" in tool.parameters["properties"]

    def test_required_parameters(self, tool):
        """Test query is required."""
        assert "query" in tool.parameters["required"]


class TestGetUserPreferencesTool:
    """Tests for GetUserPreferencesTool."""

    @pytest.fixture
    def tool(self):
        return GetUserPreferencesTool()

    def test_tool_properties(self, tool):
        """Test tool has correct properties."""
        assert tool.name == "get_user_preferences"
        assert "preferences" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_user_not_found(self, tool):
        """Test execution when user not found."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = await tool.execute(mock_db, "nonexistent-user")

        assert not result.success
        assert "not found" in result.error.lower()


class TestToolResult:
    """Tests for ToolResult."""

    def test_success_result(self):
        """Test successful result."""
        result = ToolResult(success=True, data={"items": [1, 2, 3]})

        assert result.success
        assert result.data == {"items": [1, 2, 3]}
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = ToolResult(success=False, error="Something went wrong")

        assert not result.success
        assert result.error == "Something went wrong"

    def test_to_message_success(self):
        """Test message conversion for success."""
        result = ToolResult(success=True, data={"key": "value"})
        message = result.to_message()

        assert "key" in message
        assert "value" in message

    def test_to_message_error(self):
        """Test message conversion for error."""
        result = ToolResult(success=False, error="Test error")
        message = result.to_message()

        assert "Error" in message
        assert "Test error" in message
