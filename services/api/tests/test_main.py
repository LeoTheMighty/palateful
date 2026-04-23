"""Tests for main.py application setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestApp:
    """Tests for the FastAPI app created in main.py."""

    def test_app_exists(self):
        """Test that the app is created and is a FastAPI instance."""
        from main import app
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_app_title(self):
        """Test that the app has the correct title."""
        from main import app

        assert app.title == "Palateful API"

    def test_app_version(self):
        """Test that the app has the correct version."""
        from main import app

        assert app.version == "0.1.0"

    def test_app_description(self):
        """Test that the app has a description."""
        from main import app

        assert app.description == "Recipe management and cooking assistant API"

    def test_app_has_routes(self):
        """Test that the app has registered routes."""
        from main import app

        route_paths = [r.path for r in app.routes]
        assert any("/v1" in p for p in route_paths)

    def test_health_endpoint_accessible(self, client):
        """Test that the health endpoint is accessible via the app."""
        response = client.get("/v1/health")
        assert response.status_code == 200


class TestAPIExceptionHandler:
    """Dependency-raised APIExceptions (e.g. expired Auth0 tokens in
    get_current_user) must surface as the declared status_code + the
    standard failure payload, not as an unhandled 500 that pollutes
    error_logs.
    """

    def _call_protected_endpoint(self, raising_dep) -> tuple[int, dict]:
        from main import app
        from dependencies import get_current_user

        app.dependency_overrides[get_current_user] = raising_dep
        try:
            with TestClient(app) as c:
                resp = c.get(
                    "/v1/import-jobs",
                    headers={"Authorization": "Bearer fake"},
                )
            return resp.status_code, resp.json()
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_apiexception_translates_to_declared_status(self):
        from utils.api.endpoint import APIException
        from utils.classes.error_code import ErrorCode

        async def expired():
            raise APIException(
                status_code=401,
                detail="Token has expired",
                code=ErrorCode.TOKEN_EXPIRED,
            )

        status, body = self._call_protected_endpoint(expired)

        assert status == 401
        assert body["error_code"] == ErrorCode.TOKEN_EXPIRED.value
        assert body["error_message"] == "Token has expired"
        assert body["data"] == {}

    def test_apiexception_preserves_status_and_code_for_403(self):
        from utils.api.endpoint import APIException
        from utils.classes.error_code import ErrorCode

        async def forbidden():
            raise APIException(
                status_code=403,
                detail="Admin access required",
                code=ErrorCode.FORBIDDEN,
            )

        status, body = self._call_protected_endpoint(forbidden)

        assert status == 403
        assert body["error_code"] == ErrorCode.FORBIDDEN.value
        assert body["error_message"] == "Admin access required"


class TestLifespan:
    """Tests for the app lifespan (startup/shutdown)."""

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_no_engine(self):
        """Test lifespan shutdown when db_engine is None."""
        from main import lifespan, app

        with patch("utils.services.database.db_engine", None):
            async with lifespan(app):
                pass
        # Should complete without error

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_disposes_engine(self):
        """Test lifespan shutdown disposes the db engine."""
        from main import lifespan, app

        mock_engine = MagicMock()
        with patch("utils.services.database.db_engine", mock_engine):
            async with lifespan(app):
                pass
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_engine_dispose_exception(self):
        """Test lifespan shutdown handles engine dispose exception gracefully."""
        from main import lifespan, app

        mock_engine = MagicMock()
        mock_engine.dispose.side_effect = Exception("Connection error")
        with patch("utils.services.database.db_engine", mock_engine):
            # Should not raise
            async with lifespan(app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_drain_exception_swallowed(self):
        """A crashing writer drain must not break lifespan shutdown."""
        from main import lifespan, app

        with patch(
            "utils.services.observability.get_request_writer",
            side_effect=RuntimeError("writer boom"),
        ):
            # Should not raise
            async with lifespan(app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_exits_mcp_context_cleanly(self):
        """When the inner MCP context enters successfully, __aexit__ runs on teardown."""
        import main

        exit_args: list = []

        class _CleanContext:
            async def __aenter__(self):
                return None

            async def __aexit__(self, exc_type, exc, tb):
                exit_args.append((exc_type, exc, tb))
                return False

        class _CleanApp:
            class router:
                @staticmethod
                def lifespan_context(_a):
                    return _CleanContext()

        with patch.object(main, "mcp_app", _CleanApp):
            async with main.lifespan(main.app):
                pass

        assert exit_args == [(None, None, None)]

    @pytest.mark.asyncio
    async def test_lifespan_reraises_unexpected_runtime_errors(self):
        """A RuntimeError unrelated to the session manager must propagate."""
        import main

        class _BoomContext:
            async def __aenter__(self):
                raise RuntimeError("something totally different")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class _BoomApp:
            class router:
                @staticmethod
                def lifespan_context(_a):
                    return _BoomContext()

        with patch.object(main, "mcp_app", _BoomApp):
            with pytest.raises(RuntimeError, match="something totally different"):
                async with main.lifespan(main.app):
                    pass

    @pytest.mark.asyncio
    async def test_lifespan_loads_unit_alias_cache_on_startup(self):
        """riip-1: startup hook calls reload_unit_alias_cache through Database()."""
        from main import lifespan, app

        fake_session = MagicMock()
        fake_db = MagicMock()
        fake_db.db = fake_session

        with (
            patch(
                "utils.services.database.Database",
                return_value=fake_db,
            ),
            patch(
                "utils.services.units.reload_unit_alias_cache"
            ) as mock_reload,
        ):
            async with lifespan(app):
                pass

        mock_reload.assert_called_once_with(fake_session)
        fake_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_unit_alias_cache_failure_is_swallowed(self, caplog):
        """riip-1: a failing cache reload must not break startup; it logs and continues."""
        import logging
        from main import lifespan, app

        with (
            patch(
                "utils.services.database.Database",
                side_effect=RuntimeError("pg is napping"),
            ),
            caplog.at_level(logging.ERROR, logger="main"),
        ):
            async with lifespan(app):
                pass

        assert any(
            "Failed to load unit_alias cache" in rec.message
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    async def test_lifespan_warms_async_engine_on_startup(self):
        """aam-1: startup runs SELECT 1 on the async engine to prime asyncpg's
        prepared-statement cache. Confirms the happy path (connect + execute)."""
        from main import lifespan, app

        fake_conn = AsyncMock()
        fake_conn.execute = AsyncMock()

        class _FakeConnCM:
            async def __aenter__(self_inner):
                return fake_conn

            async def __aexit__(self_inner, exc_type, exc, tb):
                return None

        fake_engine = MagicMock()
        fake_engine.connect = MagicMock(return_value=_FakeConnCM())
        fake_engine.dispose = AsyncMock(return_value=None)

        with patch("utils.services.database.async_db_engine", fake_engine):
            async with lifespan(app):
                pass

        fake_conn.execute.assert_awaited()
        fake_engine.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_async_warmup_failure_is_swallowed(self, caplog):
        """aam-1: warm-up failure falls back to lazy init on first request —
        never breaks startup."""
        import logging
        from main import lifespan, app

        fake_engine = MagicMock()
        fake_engine.connect = MagicMock(side_effect=RuntimeError("no pg today"))
        fake_engine.dispose = AsyncMock(return_value=None)

        with (
            patch("utils.services.database.async_db_engine", fake_engine),
            caplog.at_level(logging.ERROR, logger="main"),
        ):
            async with lifespan(app):
                pass

        assert any(
            "Async engine warm-up failed" in rec.message
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_disposes_async_engine(self):
        """aam-1: shutdown awaits dispose() on the async engine (reverse
        startup order — async first, sync second)."""
        from main import lifespan, app

        fake_async_engine = MagicMock()
        fake_async_engine.connect = MagicMock(side_effect=Exception("skip warmup"))
        fake_async_engine.dispose = AsyncMock(return_value=None)

        with patch("utils.services.database.async_db_engine", fake_async_engine):
            async with lifespan(app):
                pass

        fake_async_engine.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_async_dispose_failure_is_swallowed(self):
        """aam-1: async engine dispose failure must not break shutdown —
        sync engine dispose still needs to run."""
        from main import lifespan, app

        fake_async_engine = MagicMock()
        fake_async_engine.connect = MagicMock(side_effect=Exception("skip warmup"))
        fake_async_engine.dispose = AsyncMock(
            side_effect=RuntimeError("async dispose boom")
        )
        fake_sync_engine = MagicMock()

        with (
            patch("utils.services.database.async_db_engine", fake_async_engine),
            patch("utils.services.database.db_engine", fake_sync_engine),
        ):
            # Should not raise
            async with lifespan(app):
                pass

        fake_sync_engine.dispose.assert_called_once()
