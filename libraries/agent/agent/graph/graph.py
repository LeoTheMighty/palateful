"""LangGraph state graph definition for the suggestion agent."""

import logging

from langgraph.graph import StateGraph, END

from agent.graph.state import SuggestionState
from agent.graph import nodes

logger = logging.getLogger(__name__)


def create_suggestion_graph() -> StateGraph:
    """
    Create the LangGraph state graph for meal suggestions.

    The workflow is:
    1. fetch_context: Get user's pantry, preferences, expiring items
    2. generate_suggestions: Use LLM to create personalized suggestions
    3. create_notifications: Save suggestions and send notifications

    Returns:
        StateGraph ready for execution
    """
    # Create the graph
    graph = StateGraph(SuggestionState)

    # Add nodes
    graph.add_node("fetch_context", nodes.fetch_context)
    graph.add_node("generate_suggestions", nodes.generate_suggestions)
    graph.add_node("create_notifications", nodes.create_notifications)
    graph.add_node("handle_error", nodes.handle_error)

    # Define edges
    graph.add_edge("fetch_context", "generate_suggestions")
    graph.add_edge("generate_suggestions", "create_notifications")
    graph.add_edge("create_notifications", END)
    graph.add_edge("handle_error", END)

    # Set entry point
    graph.set_entry_point("fetch_context")

    return graph


def create_compiled_graph():
    """
    Create and compile the suggestion graph.

    Returns:
        Compiled graph ready for invocation
    """
    graph = create_suggestion_graph()
    return graph.compile()
