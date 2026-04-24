"""MCP tools for recipe books — list, read, create.

aam-11: tool functions are now `async def` and dispatch through
`await call_endpoint_async(...)`.
"""

from __future__ import annotations

from api.v1.recipe_book.create_recipe_book import CreateRecipeBook
from api.v1.recipe_book.get_recipe_book import GetRecipeBook
from api.v1.recipe_book.list_recipe_books import ListRecipeBooks
from mcp_server.server import call_endpoint_async, mcp


@mcp.tool()
async def list_recipe_books(limit: int = 20, offset: int = 0) -> str:
    """List every recipe book the user has access to (their own and any they've
    been invited to), with member counts and recipe counts. Use this when the
    user asks "which books do I have?" or needs to choose one.
    """
    return await call_endpoint_async(
        ListRecipeBooks, limit=limit, offset=offset
    )


@mcp.tool()
async def get_recipe_book(book_id: str) -> str:
    """Fetch a single recipe book's details, including its member list, roles,
    and a summary of recipes inside. Use before inviting someone or checking
    who can see what.
    """
    return await call_endpoint_async(GetRecipeBook, recipe_book_id=book_id)


@mcp.tool()
async def create_recipe_book(
    name: str,
    description: str | None = None,
    is_shared: bool = False,
) -> str:
    """Create a new recipe book. Set `is_shared=True` if the user wants to
    invite collaborators; otherwise it stays private to them.
    """
    params = CreateRecipeBook.Params(
        name=name, description=description, is_shared=is_shared
    )
    return await call_endpoint_async(CreateRecipeBook, params=params)
