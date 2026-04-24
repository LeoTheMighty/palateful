"""MCP tools for shopping lists."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from api.v1.shopping_list.add_item import AddShoppingListItem
from api.v1.shopping_list.create_shopping_list import CreateShoppingList
from api.v1.shopping_list.get_shopping_list import GetShoppingList
from api.v1.shopping_list.list_shopping_lists import ListShoppingLists
from api.v1.shopping_list.populate_from_recipe import PopulateFromRecipe
from api.v1.shopping_list.update_item import UpdateShoppingListItem
from mcp_server.auth import get_current_user
from mcp_server.server import call_endpoint_async, mcp


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid quantity: {value!r}") from exc


def _require_default_list(user) -> str:
    list_id = getattr(user, "default_shopping_list_id", None)
    if not list_id:
        raise ValueError(
            "No list_id provided and user has no default shopping list — "
            "ask the user which list to use"
        )
    return str(list_id)


@mcp.tool()
async def list_shopping_lists(limit: int = 20, offset: int = 0) -> str:
    """List the user's shopping lists with item counts and checked status.
    Great for a quick overview: "what lists are we working with?"
    """
    return await call_endpoint_async(ListShoppingLists, limit=limit, offset=offset)


@mcp.tool()
async def get_shopping_list(list_id: str | None = None) -> str:
    """Fetch a shopping list and all its items. If `list_id` is omitted, uses
    the user's default shopping list. Use this before adding/checking items.
    """
    user = get_current_user()
    resolved = list_id or _require_default_list(user)
    return await call_endpoint_async(GetShoppingList, list_id=resolved)


@mcp.tool()
async def create_shopping_list(name: str) -> str:
    """Create a new shopping list named `name`. The user can then add items or
    populate it from a recipe. No default-list magic here — this always makes
    a fresh list.
    """
    params = CreateShoppingList.Params(name=name)
    return await call_endpoint_async(CreateShoppingList, params=params)


@mcp.tool()
async def add_shopping_list_item(
    name: str,
    list_id: str | None = None,
    quantity: str | None = None,
    unit: str | None = None,
    category: str | None = None,
) -> str:
    """Add a single item to a shopping list. `list_id` defaults to the user's
    default shopping list. `quantity` accepts strings like "2" or "1.5" (they
    get parsed as Decimal).
    """
    user = get_current_user()
    resolved = list_id or _require_default_list(user)
    params = AddShoppingListItem.Params(
        name=name,
        quantity=_decimal_or_none(quantity),
        unit=unit,
        category=category,
    )
    return await call_endpoint_async(
        AddShoppingListItem, list_id=resolved, params=params
    )


@mcp.tool()
async def update_shopping_list_item(
    list_id: str,
    item_id: str,
    is_checked: bool | None = None,
    quantity: str | None = None,
    unit: str | None = None,
    category: str | None = None,
    name: str | None = None,
) -> str:
    """Update or check off a shopping list item. The most common use is
    `is_checked=True` to mark something bought. Only fields you pass are
    changed (partial update).
    """
    params_kwargs: dict[str, Any] = {}
    if is_checked is not None:
        params_kwargs["is_checked"] = is_checked
    if quantity is not None:
        params_kwargs["quantity"] = _decimal_or_none(quantity)
    if unit is not None:
        params_kwargs["unit"] = unit
    if category is not None:
        params_kwargs["category"] = category
    if name is not None:
        params_kwargs["name"] = name

    params = UpdateShoppingListItem.Params(**params_kwargs)
    return await call_endpoint_async(
        UpdateShoppingListItem, list_id=list_id, item_id=item_id, params=params
    )


@mcp.tool()
async def populate_from_recipe(
    recipe_id: str,
    list_id: str | None = None,
    scale_factor: float = 1.0,
) -> str:
    """Add every ingredient from a recipe to a shopping list in one go. `list_id`
    defaults to the user's default list. `scale_factor` multiplies quantities —
    use 2.0 to double a recipe, 0.5 to halve it. After this, tell the user
    "I've added all the ingredients — check the list to confirm."
    """
    user = get_current_user()
    resolved = list_id or _require_default_list(user)
    params = PopulateFromRecipe.Params(
        recipe_id=recipe_id, scale_factor=scale_factor
    )
    return await call_endpoint_async(
        PopulateFromRecipe, list_id=resolved, params=params
    )
