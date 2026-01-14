"""Agent tools for interacting with the application."""

from agent.tools.base import BaseTool, ToolResult
from agent.tools.pantry import GetPantryTool
from agent.tools.recipes import SearchRecipesTool, SuggestRecipeTool
from agent.tools.preferences import GetUserPreferencesTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "GetPantryTool",
    "SearchRecipesTool",
    "SuggestRecipeTool",
    "GetUserPreferencesTool",
]

# Tool registry for easy access
TOOLS = {
    "get_pantry": GetPantryTool,
    "search_recipes": SearchRecipesTool,
    "suggest_recipe": SuggestRecipeTool,
    "get_user_preferences": GetUserPreferencesTool,
}


def get_all_tools() -> list[BaseTool]:
    """Get instances of all available tools."""
    return [tool_class() for tool_class in TOOLS.values()]
