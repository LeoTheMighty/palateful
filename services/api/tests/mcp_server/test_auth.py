"""Tests for the MCP auth middleware."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _MockDownstreamApp:
    """Stub ASGI app that records the last scope it was called with."""

    def __init__(self):
        self.called = False
        self.user_during_call = None
        self.db_during_call = None

    async def __call__(self, scope, receive, send):
        from mcp_server.auth import current_database, current_user

        self.called = True
        self.user_during_call = current_user.get()
        self.db_during_call = current_database.get()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})


def _make_scope(headers=None):
    return {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": headers or [],
    }


def _collect_responses(messages):
    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return receive, send


class TestMCPAuthMiddleware:
    @pytest.mark.asyncio
    async def test_missing_authorization_returns_401(self):
        from mcp_server.auth import MCPAuthMiddleware

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        messages = []
        receive, send = _collect_responses(messages)
        await middleware(_make_scope([]), receive, send)

        assert not downstream.called
        assert messages[0]["status"] == 401
        body = json.loads(messages[1]["body"])
        assert "error" in body

    @pytest.mark.asyncio
    async def test_malformed_authorization_returns_401(self):
        from mcp_server.auth import MCPAuthMiddleware

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        messages = []
        receive, send = _collect_responses(messages)
        await middleware(
            _make_scope([(b"authorization", b"Token abc")]), receive, send
        )

        assert not downstream.called
        assert messages[0]["status"] == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_returns_401(self):
        from mcp_server.auth import MCPAuthMiddleware

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        messages = []
        receive, send = _collect_responses(messages)
        await middleware(
            _make_scope([(b"authorization", b"Bearer ")]), receive, send
        )

        assert messages[0]["status"] == 401

    @pytest.mark.asyncio
    async def test_valid_token_sets_contextvars_and_calls_app(self):
        from mcp_server.auth import MCPAuthMiddleware

        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_verifier = AsyncMock()
        mock_verifier.verify_token.return_value = {
            "sub": "auth0|123",
            "email": "u@example.com",
            "name": "U",
        }

        mock_database = MagicMock()
        mock_database.find_or_create_by.return_value = mock_user

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        with patch("mcp_server.auth.Database", return_value=mock_database), patch(
            "utils.services.auth0.get_auth0_verifier", return_value=mock_verifier
        ):
            messages = []
            receive, send = _collect_responses(messages)
            await middleware(
                _make_scope([(b"authorization", b"Bearer valid.jwt.token")]),
                receive,
                send,
            )

        assert downstream.called
        assert downstream.user_during_call is mock_user
        assert downstream.db_during_call is mock_database
        mock_database.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_other_headers_do_not_match_authorization(self):
        """Exercise the non-authorization branch in _get_authorization_header."""
        from mcp_server.auth import MCPAuthMiddleware

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        messages = []
        receive, send = _collect_responses(messages)
        await middleware(
            _make_scope(
                [
                    (b"content-type", b"application/json"),
                    (b"x-forwarded-for", b"1.2.3.4"),
                ]
            ),
            receive,
            send,
        )

        assert messages[0]["status"] == 401

    @pytest.mark.asyncio
    async def test_unexpected_auth_exception_closes_database(self):
        """Non-APIException during auth should still close the DB session."""
        from mcp_server.auth import MCPAuthMiddleware

        mock_database = MagicMock()

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        mock_verifier = AsyncMock()
        mock_verifier.verify_token.side_effect = RuntimeError("jwks down")

        with patch("mcp_server.auth.Database", return_value=mock_database), patch(
            "utils.services.auth0.get_auth0_verifier", return_value=mock_verifier
        ):
            messages = []
            receive, send = _collect_responses(messages)
            await middleware(
                _make_scope([(b"authorization", b"Bearer foo.bar.baz")]),
                receive,
                send,
            )

        assert messages[0]["status"] == 500
        mock_database.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_http_scope_is_passed_through(self):
        from mcp_server.auth import MCPAuthMiddleware

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        # lifespan scope should pass through untouched
        async def send(message):
            pass

        async def receive():
            return {"type": "lifespan.startup"}

        await middleware({"type": "lifespan"}, receive, send)
        assert downstream.called

    @pytest.mark.asyncio
    async def test_e2e_token_bypass_when_enabled(self):
        from mcp_server.auth import MCPAuthMiddleware

        mock_user = MagicMock()
        mock_user.id = "e2e-user"
        mock_database = MagicMock()
        mock_database.find_or_create_by.return_value = mock_user

        downstream = _MockDownstreamApp()
        middleware = MCPAuthMiddleware(downstream)

        with patch("mcp_server.auth.settings") as mock_settings, patch(
            "mcp_server.auth.Database", return_value=mock_database
        ):
            mock_settings.e2e_test_mode = True
            mock_settings.environment = "test"
            messages = []
            receive, send = _collect_responses(messages)
            await middleware(
                _make_scope([(b"authorization", b"Bearer e2e-test-token")]),
                receive,
                send,
            )

        assert downstream.called
        assert downstream.user_during_call is mock_user


class TestAuthHelpers:
    def test_get_current_user_raises_when_unset(self):
        from mcp_server.auth import get_current_user

        with pytest.raises(Exception):
            get_current_user()

    def test_get_current_database_raises_when_unset(self):
        from mcp_server.auth import get_current_database

        with pytest.raises(Exception):
            get_current_database()
