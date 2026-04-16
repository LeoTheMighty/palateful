"""Tests for MCP recipe book tools (MCP.5)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    from mcp_server.auth import current_database, current_user

    user = MagicMock()
    database = MagicMock()
    utok = current_user.set(user)
    dtok = current_database.set(database)
    try:
        yield user, database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)


class TestRecipeBookTools:
    def test_list_recipe_books(self, mcp_context):
        from mcp_server.tools.recipe_books import list_recipe_books

        with patch("mcp_server.tools.recipe_books.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            list_recipe_books(limit=5, offset=10)
        kwargs = mock_call.call_args.kwargs
        assert kwargs == {"limit": 5, "offset": 10}

    def test_get_recipe_book(self, mcp_context):
        from mcp_server.tools.recipe_books import get_recipe_book

        with patch("mcp_server.tools.recipe_books.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            get_recipe_book("b1")
        assert mock_call.call_args.kwargs == {"recipe_book_id": "b1"}

    def test_create_recipe_book_default_args(self, mcp_context):
        from mcp_server.tools.recipe_books import create_recipe_book

        with patch("mcp_server.tools.recipe_books.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            create_recipe_book("My Book")
        params = mock_call.call_args.kwargs["params"]
        assert params.name == "My Book"
        assert params.description is None
        assert params.is_shared is False

    def test_create_recipe_book_shared(self, mcp_context):
        from mcp_server.tools.recipe_books import create_recipe_book

        with patch("mcp_server.tools.recipe_books.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            create_recipe_book("Shared Book", description="family", is_shared=True)
        params = mock_call.call_args.kwargs["params"]
        assert params.description == "family"
        assert params.is_shared is True


class TestRegistration:
    def test_recipe_book_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        assert {"list_recipe_books", "get_recipe_book", "create_recipe_book"}.issubset(
            names
        )
