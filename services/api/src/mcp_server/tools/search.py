"""MCP search tools — cross-entity search and ingredient lookup."""

from __future__ import annotations

from api.v1.ingredient.search_ingredients import SearchIngredients
from api.v1.search.unified_search import UnifiedSearch
from mcp_server.server import call_endpoint, mcp


@mcp.tool()
def unified_search(
    q: str,
    limit: int = 20,
    book_id: str | None = None,
    tags: str | None = None,
    max_prep_time: int | None = None,
    max_cook_time: int | None = None,
) -> str:
    """Search across the user's recipes, publicly shared recipes, and other
    users at once. Use this for open-ended queries ("find something Italian")
    — for tightly-scoped recipe search, prefer `search_recipes` which handles
    the user's own books with semantic ranking.

    `tags` is a comma-separated string (e.g., "quick,vegetarian"). Time
    filters are in minutes.
    """
    kwargs: dict = {"q": q, "limit": limit}
    if book_id is not None:
        kwargs["book_id"] = book_id
    if tags is not None:
        kwargs["tags"] = tags
    if max_prep_time is not None:
        kwargs["max_prep_time"] = max_prep_time
    if max_cook_time is not None:
        kwargs["max_cook_time"] = max_cook_time
    return call_endpoint(UnifiedSearch, **kwargs)


@mcp.tool()
def search_ingredients(q: str, limit: int = 10) -> str:
    """Find ingredients by name — fuzzy + semantic match. Useful for "do I
    have X in my pantry?" when paired with `get_pantry`, or to disambiguate
    names before creating a recipe manually. Returns matches with a
    similarity score.
    """
    return call_endpoint(SearchIngredients, q=q, limit=limit)
