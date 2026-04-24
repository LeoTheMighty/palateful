"""Tests for MCP shopping list tools (MCP.5).

aam-13: tools are `async def` and dispatch through `call_endpoint_async`.
Tests are `async def` and `await` the tool; patch target flips to
`call_endpoint_async` with `new_callable=AsyncMock`.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    from mcp_server.auth import current_database, current_user

    user = MagicMock()
    user.id = "user-s"
    user.default_shopping_list_id = "default-list"
    database = MagicMock()
    utok = current_user.set(user)
    dtok = current_database.set(database)
    try:
        yield user, database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)


class TestShoppingListTools:
    async def test_list_shopping_lists(self, mcp_context):
        from mcp_server.tools.shopping import list_shopping_lists

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await list_shopping_lists(limit=5, offset=10)
        assert mock_call.call_args.kwargs == {"limit": 5, "offset": 10}

    async def test_get_shopping_list_default(self, mcp_context):
        from mcp_server.tools.shopping import get_shopping_list

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await get_shopping_list()
        assert mock_call.call_args.kwargs == {"list_id": "default-list"}

    async def test_get_shopping_list_explicit(self, mcp_context):
        from mcp_server.tools.shopping import get_shopping_list

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await get_shopping_list(list_id="l2")
        assert mock_call.call_args.kwargs == {"list_id": "l2"}

    async def test_get_shopping_list_no_default_raises(self, mcp_context):
        user, _ = mcp_context
        user.default_shopping_list_id = None
        from mcp_server.tools.shopping import get_shopping_list

        with pytest.raises(ValueError, match="no default shopping list"):
            await get_shopping_list()

    async def test_create_shopping_list(self, mcp_context):
        from mcp_server.tools.shopping import create_shopping_list

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await create_shopping_list("Weekly groceries")
        params = mock_call.call_args.kwargs["params"]
        assert params.name == "Weekly groceries"

    async def test_add_item_with_defaults(self, mcp_context):
        from mcp_server.tools.shopping import add_shopping_list_item

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await add_shopping_list_item(name="Eggs")
        kwargs = mock_call.call_args.kwargs
        assert kwargs["list_id"] == "default-list"
        assert kwargs["params"].name == "Eggs"
        assert kwargs["params"].quantity is None

    async def test_add_item_with_quantity_and_unit(self, mcp_context):
        from mcp_server.tools.shopping import add_shopping_list_item

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await add_shopping_list_item(
                name="Milk",
                list_id="l2",
                quantity="2",
                unit="gal",
                category="dairy",
            )
        kwargs = mock_call.call_args.kwargs
        assert kwargs["list_id"] == "l2"
        assert kwargs["params"].quantity == Decimal("2")
        assert kwargs["params"].unit == "gal"
        assert kwargs["params"].category == "dairy"

    async def test_add_item_bad_quantity_raises(self, mcp_context):
        from mcp_server.tools.shopping import add_shopping_list_item

        with pytest.raises(ValueError, match="Invalid quantity"):
            await add_shopping_list_item(name="x", quantity="not a number")

    async def test_update_item_partial(self, mcp_context):
        from mcp_server.tools.shopping import update_shopping_list_item

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await update_shopping_list_item(
                list_id="l1", item_id="i1", is_checked=True
            )
        kwargs = mock_call.call_args.kwargs
        assert kwargs["list_id"] == "l1"
        assert kwargs["item_id"] == "i1"
        assert kwargs["params"].is_checked is True
        assert kwargs["params"].quantity is None

    async def test_update_item_all_fields(self, mcp_context):
        from mcp_server.tools.shopping import update_shopping_list_item

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await update_shopping_list_item(
                list_id="l1",
                item_id="i1",
                is_checked=False,
                quantity="3",
                unit="cup",
                category="produce",
                name="Apples",
            )
        params = mock_call.call_args.kwargs["params"]
        assert params.is_checked is False
        assert params.quantity == Decimal("3")
        assert params.unit == "cup"
        assert params.category == "produce"
        assert params.name == "Apples"

    async def test_update_item_bad_quantity(self, mcp_context):
        from mcp_server.tools.shopping import update_shopping_list_item

        with pytest.raises(ValueError, match="Invalid quantity"):
            await update_shopping_list_item(list_id="l1", item_id="i1", quantity="nope")

    async def test_populate_from_recipe_defaults(self, mcp_context):
        from mcp_server.tools.shopping import populate_from_recipe

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await populate_from_recipe(recipe_id="r1")
        kwargs = mock_call.call_args.kwargs
        assert kwargs["list_id"] == "default-list"
        assert kwargs["params"].recipe_id == "r1"
        assert kwargs["params"].scale_factor == 1.0

    async def test_populate_from_recipe_explicit_list_and_scale(self, mcp_context):
        from mcp_server.tools.shopping import populate_from_recipe

        with patch(
            "mcp_server.tools.shopping.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await populate_from_recipe(recipe_id="r1", list_id="l2", scale_factor=2.0)
        kwargs = mock_call.call_args.kwargs
        assert kwargs["list_id"] == "l2"
        assert kwargs["params"].scale_factor == 2.0


class TestRegistration:
    def test_shopping_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        for expected in {
            "list_shopping_lists",
            "get_shopping_list",
            "create_shopping_list",
            "add_shopping_list_item",
            "update_shopping_list_item",
            "populate_from_recipe",
        }:
            assert expected in names
