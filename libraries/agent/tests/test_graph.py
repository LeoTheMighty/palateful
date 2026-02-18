"""Tests for the LangGraph agent."""

from unittest.mock import MagicMock, patch

from agent.graph.graph import create_suggestion_graph
from agent.graph.state import SuggestionOutput, SuggestionState


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

    def test_graph_has_entry_node(self):
        """Test graph includes the fetch_context entry node."""
        graph = create_suggestion_graph()
        # Verify fetch_context is a node (set_entry_point was called)
        assert "fetch_context" in graph.nodes


class TestAgentNodes:
    """Tests for agent node functions."""

    def test_fetch_context(self):
        """Test fetch_context node."""
        from agent.graph.nodes import fetch_context

        state: SuggestionState = {
            "user_id": "test-user",
            "trigger_type": "daily",
            "trigger_context": {},
        }

        mock_db = MagicMock()

        # Mock pantry tool (synchronous)
        with patch("agent.graph.nodes.GetPantryTool") as mock_pantry:
            mock_pantry.return_value.execute.return_value = MagicMock(
                success=True,
                data={"items": [{"ingredient_name": "tomato", "category": "produce"}]},
            )

            with patch("agent.graph.nodes.GetUserPreferencesTool") as mock_prefs:
                mock_prefs.return_value.execute.return_value = MagicMock(
                    success=True,
                    data={"dietary_restrictions": []},
                )

                result = fetch_context(state, mock_db)

        assert result["current_step"] == "context_fetched"
        assert "pantry_items" in result

    def test_handle_error(self):
        """Test handle_error node."""
        from agent.graph.nodes import handle_error

        state: SuggestionState = {
            "user_id": "test-user",
            "error": "Test error message",
        }

        mock_db = MagicMock()

        result = handle_error(state, mock_db)

        assert result["current_step"] == "error"
        assert result["error"] == "Test error message"
