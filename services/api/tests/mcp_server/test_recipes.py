"""Tests for MCP recipe tools (MCP.3).

Post-`epic-ingredients-string-simplification`: MCP recipe create/update
tools no longer consult a pg_trgm matcher. Every ingredient name inserts
a fresh `ingredients` row via `_create_ingredient_for_name` (sync
sibling) or `_create_ingredient_for_name_async` (used by the async
tools post-aam-12b). These tests assert that contract directly.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    from mcp_server.auth import (
        current_database,
        current_database_async,
        current_user,
    )

    user = MagicMock()
    user.id = "user-r"
    user.default_recipe_book_id = "default-book"
    database = MagicMock()
    async_database = MagicMock()
    async_database.db = MagicMock()
    async_database.db.add = MagicMock()
    async_database.db.flush = AsyncMock()

    utok = current_user.set(user)
    dtok = current_database.set(database)
    adtok = current_database_async.set(async_database)
    try:
        yield user, database, async_database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)
        current_database_async.reset(adtok)


class TestCreateIngredientForName:
    """`_create_ingredient_for_name` stages a fresh row, no matching."""

    def test_strips_whitespace_and_lowercases(self, mcp_context):
        _, database, _ = mcp_context
        from mcp_server.tools.recipes import _create_ingredient_for_name

        with patch("mcp_server.tools.recipes.Ingredient") as MockIngredient:
            inst = MagicMock()
            inst.id = "new-ing-id"
            MockIngredient.return_value = inst
            result = _create_ingredient_for_name("  OLIVE Oil  ", database)

        MockIngredient.assert_called_once_with(canonical_name="olive oil")
        database.db.add.assert_called_once_with(inst)
        database.db.flush.assert_called_once()
        assert result == "new-ing-id"

    def test_empty_name_raises(self, mcp_context):
        _, database, _ = mcp_context
        from mcp_server.tools.recipes import _create_ingredient_for_name

        with pytest.raises(ValueError, match="cannot be empty"):
            _create_ingredient_for_name("   ", database)


class TestCreateIngredientForNameAsync:
    """`_create_ingredient_for_name_async` mirrors the sync helper but
    awaits `session.flush()` so the INSERT lands before the caller reads
    `ingredient.id`."""

    async def test_strips_whitespace_and_lowercases(self, mcp_context):
        _, _, async_database = mcp_context
        from mcp_server.tools.recipes import _create_ingredient_for_name_async

        with patch("mcp_server.tools.recipes.Ingredient") as MockIngredient:
            inst = MagicMock()
            inst.id = "new-ing-id"
            MockIngredient.return_value = inst
            result = await _create_ingredient_for_name_async(
                "  OLIVE Oil  ", async_database
            )

        MockIngredient.assert_called_once_with(canonical_name="olive oil")
        async_database.db.add.assert_called_once_with(inst)
        async_database.db.flush.assert_awaited_once()
        assert result == "new-ing-id"

    async def test_empty_name_raises(self, mcp_context):
        _, _, async_database = mcp_context
        from mcp_server.tools.recipes import _create_ingredient_for_name_async

        with pytest.raises(ValueError, match="cannot be empty"):
            await _create_ingredient_for_name_async("   ", async_database)


class TestSimpleRecipeTools:
    async def test_get_recipe_delegates_to_call_endpoint_async(self, mcp_context):
        from mcp_server.tools.recipes import get_recipe

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = '{"id":"r1"}'
            result = await get_recipe("r1")
        assert result == '{"id":"r1"}'
        args, kwargs = mock_call.call_args
        assert kwargs == {"recipe_id": "r1"}

    async def test_list_recipes_uses_default_book(self, mcp_context):
        from mcp_server.tools.recipes import list_recipes

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await list_recipes()
        kwargs = mock_call.call_args.kwargs
        assert kwargs["book_id"] == "default-book"
        assert kwargs["limit"] == 20

    async def test_list_recipes_uses_explicit_book(self, mcp_context):
        from mcp_server.tools.recipes import list_recipes

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await list_recipes(book_id="b2", limit=5, offset=10, search="soup")
        kwargs = mock_call.call_args.kwargs
        assert kwargs == {
            "book_id": "b2",
            "limit": 5,
            "offset": 10,
            "search": "soup",
        }

    async def test_list_recipes_no_default_raises(self, mcp_context):
        from mcp_server.tools.recipes import list_recipes

        user, _, _ = mcp_context
        user.default_recipe_book_id = None
        with pytest.raises(ValueError, match="no default recipe book"):
            await list_recipes()

    async def test_delete_recipe(self, mcp_context):
        """aam-12b: DeleteRecipe is async — tool dispatches through
        `await call_endpoint_async(...)`."""
        from mcp_server.tools.recipes import delete_recipe

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await delete_recipe("r1")
        assert mock_call.call_args.kwargs == {"recipe_id": "r1"}

    async def test_toggle_favorite(self, mcp_context):
        from mcp_server.tools.recipes import toggle_favorite

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await toggle_favorite("r1")
        assert mock_call.call_args.kwargs == {"recipe_id": "r1"}

    async def test_list_favorites(self, mcp_context):
        """aam-10: ListFavorites is async — tool dispatches through
        `await call_endpoint_async(...)`."""
        from mcp_server.tools.recipes import list_favorites

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await list_favorites()
        # No kwargs needed
        assert mock_call.called

    async def test_fork_recipe_uses_default_book(self, mcp_context):
        """aam-12b: ForkRecipe is async — tool dispatches through
        `await call_endpoint_async(...)`."""
        from mcp_server.tools.recipes import fork_recipe

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await fork_recipe("r1")
        kwargs = mock_call.call_args.kwargs
        assert kwargs["recipe_id"] == "r1"
        assert kwargs["params"].destination_book_id == "default-book"

    async def test_fork_recipe_explicit_destination(self, mcp_context):
        from mcp_server.tools.recipes import fork_recipe

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await fork_recipe("r1", destination_book_id="b2")
        kwargs = mock_call.call_args.kwargs
        assert kwargs["params"].destination_book_id == "b2"


class TestCreateRecipe:
    async def test_mcp_create_recipe_always_creates_new_ingredient_rows(
        self, mcp_context
    ):
        """Every MCP `create_recipe` call stages a fresh row per name —
        no find-or-create, no cross-recipe identity (str-ing-2).

        aam-12b: switched to the async ingredient helper + endpoint."""
        from mcp_server.tools.recipes import create_recipe

        with patch(
            "mcp_server.tools.recipes._create_ingredient_for_name_async",
            new_callable=AsyncMock,
            side_effect=["fresh-ing-1", "fresh-ing-2"],
        ) as mock_create, patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = '{"id":"new-recipe"}'
            result = await create_recipe(
                name="Pasta",
                ingredients=[
                    {"name": "tomato", "quantity": "2", "unit": "cup"},
                    {"name": "tomato", "quantity": "1", "unit": "cup"},
                ],
                steps=[{"instruction": "Boil water"}],
                prep_time=5,
                cook_time=15,
                servings=2,
                tags=["dinner"],
            )

        assert result == '{"id":"new-recipe"}'
        # Both entries even though they share a name — no dedup.
        assert mock_create.call_count == 2
        params = mock_call.call_args.kwargs["params"]
        assert params.ingredients[0].ingredient_id == "fresh-ing-1"
        assert params.ingredients[1].ingredient_id == "fresh-ing-2"
        assert params.ingredients[0].quantity == Decimal("2")
        assert params.steps[0].instruction == "Boil water"

    async def test_invalid_ingredient_missing_name(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="needs a `name`"):
            await create_recipe(
                name="X",
                ingredients=[{"quantity": "1", "unit": "cup"}],
            )

    async def test_invalid_ingredient_non_dict(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="must be an object"):
            await create_recipe(name="X", ingredients=["just a string"])

    async def test_invalid_ingredient_missing_quantity(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="missing a quantity"):
            await create_recipe(
                name="X",
                ingredients=[{"name": "flour", "unit": "cup"}],
            )

    async def test_invalid_ingredient_missing_unit(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="missing a unit"):
            await create_recipe(
                name="X",
                ingredients=[{"name": "flour", "quantity": "1"}],
            )

    async def test_invalid_step_non_dict(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="Each step must be an object"):
            await create_recipe(name="X", steps=["cook it"])

    async def test_invalid_step_missing_instruction(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="missing an `instruction`"):
            await create_recipe(name="X", steps=[{"active_time_minutes": 5}])

    async def test_invalid_quantity(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with patch(
            "mcp_server.tools.recipes._create_ingredient_for_name_async",
            new_callable=AsyncMock,
            return_value="i1",
        ), pytest.raises(ValueError, match="Invalid quantity"):
            await create_recipe(
                name="X",
                ingredients=[{"name": "flour", "quantity": "abc", "unit": "cup"}],
            )

    async def test_no_default_book_and_no_arg_raises(self, mcp_context):
        user, _, _ = mcp_context
        user.default_recipe_book_id = None
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="no default recipe book"):
            await create_recipe(name="X")


class TestUpdateRecipe:
    async def test_partial_update_without_ingredients(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await update_recipe(recipe_id="r1", name="New Name", description="New desc")

        params = mock_call.call_args.kwargs["params"]
        assert params.name == "New Name"
        assert params.description == "New desc"
        # unset fields stay None
        assert params.servings is None
        assert params.ingredients is None

    async def test_mcp_update_recipe_always_creates_new_ingredient_rows(
        self, mcp_context
    ):
        from mcp_server.tools.recipes import update_recipe

        with patch(
            "mcp_server.tools.recipes._create_ingredient_for_name_async",
            new_callable=AsyncMock,
            return_value="ing-1",
        ), patch(
            "mcp_server.tools.recipes.call_endpoint_async",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = "{}"
            await update_recipe(
                recipe_id="r1",
                ingredients=[
                    {"name": "salt", "quantity": "1", "unit": "tsp"},
                ],
                steps=[{"instruction": "mix"}],
                instructions="all steps",
                prep_time=5,
                cook_time=10,
                servings=2,
                tags=["quick"],
            )

        params = mock_call.call_args.kwargs["params"]
        assert params.ingredients[0].ingredient_id == "ing-1"
        assert params.steps[0].instruction == "mix"
        assert params.instructions == "all steps"
        assert params.tags == ["quick"]

    async def test_invalid_update_ingredient_not_dict(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="must be an object"):
            await update_recipe(recipe_id="r1", ingredients=["oops"])

    async def test_invalid_update_ingredient_missing_name(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="needs a `name`"):
            await update_recipe(
                recipe_id="r1",
                ingredients=[{"quantity": "1", "unit": "cup"}],
            )

    async def test_invalid_update_ingredient_missing_quantity(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="missing a quantity"):
            await update_recipe(
                recipe_id="r1",
                ingredients=[{"name": "x", "unit": "cup"}],
            )

    async def test_invalid_update_ingredient_missing_unit(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="missing a unit"):
            await update_recipe(
                recipe_id="r1",
                ingredients=[{"name": "x", "quantity": "1"}],
            )

    async def test_invalid_update_step_not_dict(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="must be an object"):
            await update_recipe(recipe_id="r1", steps=["oops"])

    async def test_invalid_update_step_missing_instruction(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="missing `instruction`"):
            await update_recipe(recipe_id="r1", steps=[{"active_time_minutes": 5}])


class TestToolRegistration:
    def test_recipe_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        for expected in {
            "get_recipe",
            "list_recipes",
            "create_recipe",
            "update_recipe",
            "delete_recipe",
            "toggle_favorite",
            "list_favorites",
            "fork_recipe",
        }:
            assert expected in names, f"missing {expected}"
