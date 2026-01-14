"""Tests for the LangGraph agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.graph.state import SuggestionState, SuggestionOutput
from agent.graph.graph import create_suggestion_graph


class TestSuggestionState:
    """Tests for SuggestionState."""

    def test_create_initial_state(self):
        """Test creating initial state."""
        state: SuggestionState = {
            "user_id": "test-user",
            "trigger_type": "daily",
            "trigger_context": {},
            "pantry_items": [],
            "user_preferences": {},
            "expiring_items": [],
            "matched_recipes": [],
            "suggestions": [],
            "messages": [],
            "current_step": "started",
            "error": None,
            "created_suggestion_ids": [],
            "notifications_sent": 0,
        }

        assert state["user_id"] == "test-user"
        assert state["trigger_type"] == "daily"
        assert state["current_step"] == "started"


class TestSuggestionOutput:
    """Tests for SuggestionOutput."""

    def test_create_output(self):
        """Test creating suggestion output."""
        output: SuggestionOutput = {
            "title": "Test Suggestion",
            "body": "This is a test suggestion body.",
            "suggestion_type": "recipe",
            "recipe_id": None,
            "trigger_context": {"trigger_type": "daily"},
        }

        assert output["title"] == "Test Suggestion"
        assert output["suggestion_type"] == "recipe"


class TestSuggestionGraph:
    """Tests for the suggestion graph."""

    def test_create_graph(self):
        """Test creating the suggestion graph."""
        graph = create_suggestion_graph()

        assert graph is not None
        # Check nodes exist
        assert "fetch_context" in graph.nodes
        assert "generate_suggestions" in graph.nodes
        assert "create_notifications" in graph.nodes
        assert "handle_error" in graph.nodes

    def test_graph_entry_point(self):
        """Test graph has correct entry point."""
        graph = create_suggestion_graph()

        # The entry point should be fetch_context
        assert graph.entry_point == "fetch_context"


class TestAgentNodes:
    """Tests for agent node functions."""

    @pytest.mark.asyncio
    async def test_fetch_context(self):
        """Test fetch_context node."""
        from agent.graph.nodes import fetch_context

        state: SuggestionState = {
            "user_id": "test-user",
            "trigger_type": "daily",
            "trigger_context": {},
        }

        mock_db = AsyncMock()

        # Mock pantry tool
        with patch("agent.graph.nodes.GetPantryTool") as mock_pantry:
            mock_pantry.return_value.execute = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    data={"items": [{"ingredient_name": "tomato", "category": "produce"}]},
                )
            )

            with patch("agent.graph.nodes.GetUserPreferencesTool") as mock_prefs:
                mock_prefs.return_value.execute = AsyncMock(
                    return_value=MagicMock(
                        success=True,
                        data={"dietary_restrictions": []},
                    )
                )

                result = await fetch_context(state, mock_db)

        assert result["current_step"] == "context_fetched"
        assert "pantry_items" in result

    @pytest.mark.asyncio
    async def test_handle_error(self):
        """Test handle_error node."""
        from agent.graph.nodes import handle_error

        state: SuggestionState = {
            "user_id": "test-user",
            "error": "Test error message",
        }

        mock_db = AsyncMock()

        result = await handle_error(state, mock_db)

        assert result["current_step"] == "error"
        assert result["error"] == "Test error message"
