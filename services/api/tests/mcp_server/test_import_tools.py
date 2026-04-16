"""Tests for MCP import tools (MCP.4)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mcp_context():
    from mcp_server.auth import current_database, current_user

    user = MagicMock()
    user.id = "user-i"
    user.default_recipe_book_id = "default-book"
    database = MagicMock()

    utok = current_user.set(user)
    dtok = current_database.set(database)
    try:
        yield user, database
    finally:
        current_user.reset(utok)
        current_database.reset(dtok)


class TestBuildStartImportParams:
    def test_url_requires_url(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        with pytest.raises(ValueError, match="`url` is required"):
            _build_start_import_params(
                "url", url=None, text=None, ocr_texts=None, additional_context=None
            )

    def test_url_success(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        params = _build_start_import_params(
            "url",
            url=" https://x.com/recipe ",
            text=None,
            ocr_texts=None,
            additional_context=None,
        )
        assert params.source_type == "url"
        assert params.url == "https://x.com/recipe"

    def test_text_requires_text(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        with pytest.raises(ValueError, match="`text` is required"):
            _build_start_import_params(
                "text", url=None, text="   ", ocr_texts=None, additional_context=None
            )

    def test_text_success_without_context(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        params = _build_start_import_params(
            "text",
            url=None,
            text="Recipe text",
            ocr_texts=None,
            additional_context=None,
        )
        assert params.source_type == "text"
        assert params.raw_text == "Recipe text"

    def test_text_appends_additional_context(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        params = _build_start_import_params(
            "text",
            url=None,
            text="Recipe text",
            ocr_texts=None,
            additional_context=" from mom's cookbook ",
        )
        assert "Additional context: from mom's cookbook" in params.raw_text

    def test_photo_requires_ocr_texts(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        with pytest.raises(ValueError, match="ocr_texts"):
            _build_start_import_params(
                "photo",
                url=None,
                text=None,
                ocr_texts=["  ", None],
                additional_context=None,
            )

    def test_photo_success_filters_blanks(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        params = _build_start_import_params(
            "photo",
            url=None,
            text=None,
            ocr_texts=[" one ", "", None, "two"],
            additional_context=None,
        )
        assert params.source_type == "photo"
        assert params.ocr_texts == ["one", "two"]

    def test_unknown_source_type_raises(self):
        from mcp_server.tools.import_tools import _build_start_import_params

        with pytest.raises(ValueError, match="Unsupported source_type"):
            _build_start_import_params(
                "magic",
                url=None,
                text=None,
                ocr_texts=None,
                additional_context=None,
            )


class TestImportRecipe:
    def test_delegates_url_with_default_book(self, mcp_context):
        from mcp_server.tools.import_tools import import_recipe

        with patch("mcp_server.tools.import_tools.call_endpoint") as mock_call:
            mock_call.return_value = '{"id":"job1"}'
            result = import_recipe(source_type="url", url="https://a.com/recipe")

        assert result == '{"id":"job1"}'
        kwargs = mock_call.call_args.kwargs
        assert kwargs["book_id"] == "default-book"
        assert kwargs["params"].source_type == "url"

    def test_explicit_book_id(self, mcp_context):
        from mcp_server.tools.import_tools import import_recipe

        with patch("mcp_server.tools.import_tools.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            import_recipe(source_type="text", text="boil water", book_id="b9")

        assert mock_call.call_args.kwargs["book_id"] == "b9"

    def test_no_default_book_raises(self, mcp_context):
        user, _ = mcp_context
        user.default_recipe_book_id = None
        from mcp_server.tools.import_tools import import_recipe

        with pytest.raises(ValueError, match="no default recipe book"):
            import_recipe(source_type="url", url="https://x.com/y")


class _FakeOkEndpoint:
    """Replaces GetImportJob / ListImportItems with a successful stub."""

    def __init__(self, database=None, user=None):
        pass

    def run(self, **kwargs):
        return {
            "success": True,
            "data": SimpleNamespace(id="job1", status="pending"),
            "status": 200,
        }


class _FakeItemsOk:
    def __init__(self, database=None, user=None):
        pass

    def run(self, **kwargs):
        return {
            "success": True,
            "data": SimpleNamespace(items=[], total=0, has_more=False),
            "status": 200,
        }


class TestGetImportStatus:
    def test_combines_job_and_items(self, mcp_context):
        from mcp_server.tools.import_tools import get_import_status

        with patch(
            "mcp_server.tools.import_tools.GetImportJob", _FakeOkEndpoint
        ), patch(
            "mcp_server.tools.import_tools.ListImportItems", _FakeItemsOk
        ):
            raw = get_import_status("job1")

        parsed = json.loads(raw)
        assert "job" in parsed
        assert "items" in parsed
        assert parsed["job"]["id"] == "job1"

    def test_job_failure_returns_error(self, mcp_context):
        from mcp_server.tools.import_tools import get_import_status

        class _FailJob:
            def __init__(self, database=None, user=None):
                pass

            def run(self, **kwargs):
                return {"success": False, "error_message": "not found", "status": 404}

        with patch("mcp_server.tools.import_tools.GetImportJob", _FailJob):
            result = get_import_status("doesnt-exist")
        assert result.startswith("Error: not found")

    def test_items_failure_returns_error(self, mcp_context):
        from mcp_server.tools.import_tools import get_import_status

        class _FailItems:
            def __init__(self, database=None, user=None):
                pass

            def run(self, **kwargs):
                return {"success": False, "error_message": "boom", "status": 500}

        with patch(
            "mcp_server.tools.import_tools.GetImportJob", _FakeOkEndpoint
        ), patch(
            "mcp_server.tools.import_tools.ListImportItems", _FailItems
        ):
            result = get_import_status("j")
        assert result.startswith("Error: boom")


class TestApproveImport:
    def test_delegates_to_call_endpoint(self, mcp_context):
        from mcp_server.tools.import_tools import approve_import

        with patch("mcp_server.tools.import_tools.call_endpoint") as mock_call:
            mock_call.return_value = "{}"
            approve_import("i1")
        assert mock_call.call_args.kwargs == {"item_id": "i1"}


class TestRegistration:
    def test_import_tools_registered(self):
        from mcp_server import build_mcp_app, mcp

        build_mcp_app()
        names = {t.name for t in mcp._tool_manager.list_tools()}
        assert {"import_recipe", "get_import_status", "approve_import"}.issubset(names)
