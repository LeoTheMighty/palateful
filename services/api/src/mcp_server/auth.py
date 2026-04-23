"""Authentication middleware for the MCP server.

The MCP protocol is agnostic about how a request arrived; we need to do the
Bearer-JWT + user-lookup dance before MCP's own ASGI app takes over. This
middleware mirrors `dependencies.get_current_user` but stores the resolved
`User` and `Database` in Python contextvars so tool functions (which may
run on thread pool executors via asyncio.to_thread) can read them back with
`copy_context().run(...)`.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING

from config import settings
from starlette.types import ASGIApp, Receive, Scope, Send
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.services.async_database import AsyncDatabase
from utils.services.database import Database

if TYPE_CHECKING:  # pragma: no cover - typing only
    from utils.models.user import User

logger = logging.getLogger(__name__)

_E2E_TOKEN = "e2e-test-token"
_E2E_AUTH0_ID = "e2e|test-user"

current_user: ContextVar[User | None] = ContextVar("mcp_current_user", default=None)
current_database: ContextVar[Database | None] = ContextVar("mcp_current_database", default=None)
# aam-6: async sibling contextvar populated alongside the sync one when
# the MCP middleware authenticates a request. Phase 3 MCP-tool stories
# read from this via `get_current_database_async()` after they swap to
# `await call_endpoint_async(...)`. Sync `current_database` stays the
# active source of truth until every MCP tool converts (post-aam-24).
current_database_async: ContextVar[AsyncDatabase | None] = ContextVar(
    "mcp_current_database_async", default=None
)


def _unauthorized(message: str, code: int = ErrorCode.INVALID_TOKEN.value) -> dict:
    return {"error": {"code": code, "message": message}}


class MCPAuthMiddleware:
    """Starlette ASGI middleware that authenticates every MCP request.

    On success it stores `User` + `Database` in contextvars and, importantly,
    tears the database session down after the response completes so each MCP
    call has a short-lived session — matching the FastAPI dependency pattern.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        authorization = _get_authorization_header(scope)
        try:
            user, database = await _authenticate(authorization)
        except APIException as exc:
            await _send_error_response(send, exc.status_code, exc.detail, exc.code)
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected MCP auth failure")
            await _send_error_response(send, 500, f"Auth error: {exc}", ErrorCode.INTERNAL_ERROR.value)
            return

        user_token = current_user.set(user)
        db_token = current_database.set(database)
        try:
            await self.app(scope, receive, send)
        finally:
            current_user.reset(user_token)
            current_database.reset(db_token)
            try:
                database.close()
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to close MCP database session")


def _get_authorization_header(scope: Scope) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            return value.decode("latin-1")
    return None


async def _authenticate(authorization: str | None) -> tuple[User, Database]:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIException(
            status_code=401,
            detail="Missing or malformed Authorization header",
            code=ErrorCode.INVALID_TOKEN,
        )

    token = authorization[len("Bearer "):].strip()
    if not token:
        raise APIException(
            status_code=401,
            detail="Empty bearer token",
            code=ErrorCode.INVALID_TOKEN,
        )

    from utils.models.user import User

    database = Database()
    try:
        if (
            settings.e2e_test_mode
            and settings.environment in ("development", "test")
            and token == _E2E_TOKEN
        ):
            user = database.find_or_create_by(
                User,
                auth0_id=_E2E_AUTH0_ID,
                defaults={
                    "email": "e2e@palateful.test",
                    "name": "E2E Test User",
                    "has_completed_onboarding": True,
                },
            )
            return user, database

        from utils.services.auth0 import get_auth0_verifier

        verifier = get_auth0_verifier()
        claims = await verifier.verify_token(token)

        auth0_id = claims["sub"]
        user = database.find_or_create_by(
            User,
            auth0_id=auth0_id,
            defaults={
                "email": claims.get("email") or None,
                "name": claims.get("name"),
                "picture": claims.get("picture"),
                "email_verified": claims.get("email_verified", False),
            },
        )
        return user, database
    except Exception:
        database.close()
        raise


async def _send_error_response(send: Send, status: int, message: str, code: int) -> None:
    payload = json.dumps(_unauthorized(message, code)).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode("ascii")),
                (b"www-authenticate", b'Bearer realm="palateful-mcp"'),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload, "more_body": False})


def get_current_user() -> User:
    """Return the authenticated MCP user for the current request context."""
    user = current_user.get()
    if user is None:
        raise APIException(
            status_code=401,
            detail="No authenticated user in MCP context",
            code=ErrorCode.INVALID_TOKEN,
        )
    return user


def get_current_database() -> Database:
    """Return the request-scoped Database for the current MCP request."""
    database = current_database.get()
    if database is None:
        raise APIException(
            status_code=500,
            detail="No database in MCP context",
            code=ErrorCode.INTERNAL_ERROR,
        )
    return database


def get_current_database_async() -> AsyncDatabase:
    """Async sibling of `get_current_database` (aam-6).

    Returns the request-scoped `AsyncDatabase` MCP tools see after their
    domain story converts (`call_endpoint(...)` → `await
    call_endpoint_async(...)`). Until any MCP tool actually uses this,
    the contextvar stays `None` per request; once the middleware
    populates it (next aam-* MCP story), tools that switched to the
    async helper resolve the async DB transparently.
    """
    database = current_database_async.get()
    if database is None:
        raise APIException(
            status_code=500,
            detail="No async database in MCP context",
            code=ErrorCode.INTERNAL_ERROR,
        )
    return database
