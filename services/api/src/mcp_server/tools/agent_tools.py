"""MCP tools that wrap the existing agent tools (sync SQLAlchemy).

Each function delegates to `call_agent_tool()`, which jumps the call onto a
worker thread with `copy_context()` so the current user + database contextvars
propagate into the synchronous tool.
"""

from __future__ import annotations

from agent.tools.pantry import GetPantryTool
from agent.tools.preferences import GetUserPreferencesTool
from agent.tools.recipes import (
    AddNoteToRecipeTool,
    SearchRecipesTool,
    SuggestRecipeTool,
)
from mcp_server.server import call_agent_tool, mcp


@mcp.tool()
async def search_recipes(
    query: str,
    max_results: int = 5,
    max_cook_time: int | None = None,
    pantry_match: bool = False,
) -> str:
    """Search the user's recipe collection by natural language.

    Use this whenever the user asks about recipes they already have —
    "what can I make with chicken", "do I have any pasta recipes", "something
    quick for tonight". Returns relevance-scored matches with ingredients and
    cook times. Set `pantry_match=True` to restrict to recipes they can make
    with what's already in their pantry (plus up to 2 missing ingredients).
    """
    return await call_agent_tool(
        SearchRecipesTool(),
        query=query,
        max_results=max_results,
        max_cook_time=max_cook_time,
        pantry_match=pantry_match,
    )


@mcp.tool()
async def suggest_recipe(
    ingredients: list[str],
    cuisine: str | None = None,
    meal_type: str | None = None,
    dietary_restrictions: list[str] | None = None,
    difficulty: str = "medium",
) -> str:
    """Generate a brand-new recipe suggestion tailored to the user.

    Use this when the user wants ideas — "what can I make with these leftovers",
    "suggest a vegetarian dinner". The response is AI-generated structured
    recipe content (name, description, ingredients, steps, tips). It's NOT
    saved to their collection automatically — if they want to keep it, tell
    them and then use `create_recipe`.
    """
    return await call_agent_tool(
        SuggestRecipeTool(),
        ingredients=ingredients,
        cuisine=cuisine,
        meal_type=meal_type,
        dietary_restrictions=dietary_restrictions,
        difficulty=difficulty,
    )


@mcp.tool()
async def add_note_to_recipe(
    note_body: str,
    recipe_id: str | None = None,
    recipe_name: str | None = None,
) -> str:
    """Attach a cooking note, tip, or variation to a specific recipe.

    Provide either the recipe's UUID (`recipe_id`) or, more commonly, its name
    (`recipe_name`) — when only a name is given, the closest semantic match
    from the user's books is used. Good for capturing "next time, use less
    salt" or "cooked 5 extra minutes" after cooking.
    """
    return await call_agent_tool(
        AddNoteToRecipeTool(),
        note_body=note_body,
        recipe_id=recipe_id,
        recipe_name=recipe_name,
    )


@mcp.tool()
async def get_pantry(
    include_expired: bool = False,
    expiring_within_days: int | None = None,
    category: str | None = None,
) -> str:
    """List the user's current pantry — what they have on hand.

    Use this before suggesting recipes so suggestions align with what's
    actually in the kitchen. Items are sorted by soonest expiration. Set
    `expiring_within_days=3` to surface things to use up; filter `category`
    (e.g. "produce", "protein", "pantry staple") to narrow down.
    """
    return await call_agent_tool(
        GetPantryTool(),
        include_expired=include_expired,
        expiring_within_days=expiring_within_days,
        category=category,
    )


@mcp.tool()
async def get_user_preferences() -> str:
    """Return the user's dietary restrictions, cuisine preferences, and cooking settings.

    Pull this at the start of a cooking-related conversation so suggestions
    respect their diet (vegetarian, gluten-free, etc.) and match their
    household size, skill level, and typical prep-time tolerance.
    """
    return await call_agent_tool(GetUserPreferencesTool())
