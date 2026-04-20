"""Tests for MCP recipe tools (MCP.3).

Post-`epic-ingredients-string-simplification`: MCP recipe create/update
tools no longer consult a pg_trgm matcher. Every ingredient name inserts
a fresh `ingredients` row via `_create_ingredient_for_name`. These tests
assert that contract directly.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    from mcp_server.auth import current_database, current_user

    user = MagicMock()
    user.id = "user-r"
    user.default_recipe_book_id = "default-book"
    database = MagicMock()

    utok = current_user.set(user)
    dtok = current_database.set(database)
    try:
        yield user, database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)


class TestCreateIngredientForName:
    """`_create_ingredient_for_name` stages a fresh row, no matching."""

    def test_strips_whitespace_and_lowercases(self, mcp_context):
        _, database = mcp_context
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
        _, database = mcp_context
        from mcp_server.tools.recipes import _create_ingredient_for_name

        with pytest.raises(ValueError, match="cannot be empty"):
            _create_ingredient_for_name("   ", database)


class TestSimpleRecipeTools:
    def test_get_recipe_delegates_to_call_endpoint(self, mcp_context):
        from mcp_server.tools.recipes import get_recipe

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = '{"id":"r1"}'
            result = get_recipe("r1")
        assert result == '{"id":"r1"}'
        args, kwargs = mock_call.call_args
        assert kwargs == {"recipe_id": "r1"}

    def test_list_recipes_uses_default_book(self, mcp_context):
        from mcp_server.tools.recipes import list_recipes

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            list_recipes()
        kwargs = mock_call.call_args.kwargs
        assert kwargs["book_id"] == "default-book"
        assert kwargs["limit"] == 20

    def test_list_recipes_uses_explicit_book(self, mcp_context):
        from mcp_server.tools.recipes import list_recipes

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            list_recipes(book_id="b2", limit=5, offset=10, search="soup")
        kwargs = mock_call.call_args.kwargs
        assert kwargs == {
            "book_id": "b2",
            "limit": 5,
            "offset": 10,
            "search": "soup",
        }

    def test_list_recipes_no_default_raises(self, mcp_context):
        from mcp_server.tools.recipes import list_recipes

        user, _ = mcp_context
        user.default_recipe_book_id = None
        with pytest.raises(ValueError, match="no default recipe book"):
            list_recipes()

    def test_delete_recipe(self, mcp_context):
        from mcp_server.tools.recipes import delete_recipe

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            delete_recipe("r1")
        assert mock_call.call_args.kwargs == {"recipe_id": "r1"}

    def test_toggle_favorite(self, mcp_context):
        from mcp_server.tools.recipes import toggle_favorite

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            toggle_favorite("r1")
        assert mock_call.call_args.kwargs == {"recipe_id": "r1"}

    def test_list_favorites(self, mcp_context):
        from mcp_server.tools.recipes import list_favorites

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            list_favorites()
        # No kwargs needed
        assert mock_call.called

    def test_fork_recipe_uses_default_book(self, mcp_context):
        from mcp_server.tools.recipes import fork_recipe

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            fork_recipe("r1")
        kwargs = mock_call.call_args.kwargs
        assert kwargs["recipe_id"] == "r1"
        assert kwargs["params"].destination_book_id == "default-book"

    def test_fork_recipe_explicit_destination(self, mcp_context):
        from mcp_server.tools.recipes import fork_recipe

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            fork_recipe("r1", destination_book_id="b2")
        kwargs = mock_call.call_args.kwargs
        assert kwargs["params"].destination_book_id == "b2"


class TestCreateRecipe:
    def test_mcp_create_recipe_always_creates_new_ingredient_rows(
        self, mcp_context
    ):
        """Every MCP `create_recipe` call stages a fresh row per name —
        no find-or-create, no cross-recipe identity (str-ing-2)."""
        from mcp_server.tools.recipes import create_recipe

        with patch(
            "mcp_server.tools.recipes._create_ingredient_for_name",
            side_effect=["fresh-ing-1", "fresh-ing-2"],
        ) as mock_create, patch(
            "mcp_server.tools.recipes.call_endpoint"
        ) as mock_call:
            mock_call.return_value = '{"id":"new-recipe"}'
            result = create_recipe(
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

    def test_invalid_ingredient_missing_name(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="needs a `name`"):
            create_recipe(
                name="X",
                ingredients=[{"quantity": "1", "unit": "cup"}],
            )

    def test_invalid_ingredient_non_dict(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="must be an object"):
            create_recipe(name="X", ingredients=["just a string"])

    def test_invalid_ingredient_missing_quantity(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="missing a quantity"):
            create_recipe(
                name="X",
                ingredients=[{"name": "flour", "unit": "cup"}],
            )

    def test_invalid_ingredient_missing_unit(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="missing a unit"):
            create_recipe(
                name="X",
                ingredients=[{"name": "flour", "quantity": "1"}],
            )

    def test_invalid_step_non_dict(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="Each step must be an object"):
            create_recipe(name="X", steps=["cook it"])

    def test_invalid_step_missing_instruction(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="missing an `instruction`"):
            create_recipe(name="X", steps=[{"active_time_minutes": 5}])

    def test_invalid_quantity(self, mcp_context):
        from mcp_server.tools.recipes import create_recipe

        with patch(
            "mcp_server.tools.recipes._create_ingredient_for_name",
            return_value="i1",
        ), pytest.raises(ValueError, match="Invalid quantity"):
            create_recipe(
                name="X",
                ingredients=[{"name": "flour", "quantity": "abc", "unit": "cup"}],
            )

    def test_no_default_book_and_no_arg_raises(self, mcp_context):
        user, _ = mcp_context
        user.default_recipe_book_id = None
        from mcp_server.tools.recipes import create_recipe

        with pytest.raises(ValueError, match="no default recipe book"):
            create_recipe(name="X")


class TestUpdateRecipe:
    def test_partial_update_without_ingredients(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            update_recipe(recipe_id="r1", name="New Name", description="New desc")

        params = mock_call.call_args.kwargs["params"]
        assert params.name == "New Name"
        assert params.description == "New desc"
        # unset fields stay None
        assert params.servings is None
        assert params.ingredients is None

    def test_mcp_update_recipe_always_creates_new_ingredient_rows(
        self, mcp_context
    ):
        from mcp_server.tools.recipes import update_recipe

        with patch(
            "mcp_server.tools.recipes._create_ingredient_for_name",
            return_value="ing-1",
        ), patch("mcp_server.tools.recipes.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            update_recipe(
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

    def test_invalid_update_ingredient_not_dict(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="must be an object"):
            update_recipe(recipe_id="r1", ingredients=["oops"])

    def test_invalid_update_ingredient_missing_name(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="needs a `name`"):
            update_recipe(
                recipe_id="r1",
                ingredients=[{"quantity": "1", "unit": "cup"}],
            )

    def test_invalid_update_ingredient_missing_quantity(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="missing a quantity"):
            update_recipe(
                recipe_id="r1",
                ingredients=[{"name": "x", "unit": "cup"}],
            )

    def test_invalid_update_ingredient_missing_unit(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="missing a unit"):
            update_recipe(
                recipe_id="r1",
                ingredients=[{"name": "x", "quantity": "1"}],
            )

    def test_invalid_update_step_not_dict(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="must be an object"):
            update_recipe(recipe_id="r1", steps=["oops"])

    def test_invalid_update_step_missing_instruction(self, mcp_context):
        from mcp_server.tools.recipes import update_recipe

        with pytest.raises(ValueError, match="missing `instruction`"):
            update_recipe(recipe_id="r1", steps=[{"active_time_minutes": 5}])


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
