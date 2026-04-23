"""FastMCP server instance and the call_endpoint() helper.

The server exposes Palateful's existing API surface as MCP tools. Every tool
either wraps an `Endpoint` (via `call_endpoint`) or an agent `BaseTool` (via
`call_agent_tool`). There is no new business logic in the MCP layer.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextvars import copy_context
from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder
from mcp.server.fastmcp import FastMCP
from mcp_server.auth import (
    MCPAuthMiddleware,
    get_current_database,
    get_current_user,
)
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount

if TYPE_CHECKING:  # pragma: no cover - typing only
    from agent.tools.base import BaseTool
    from utils.api.endpoint import AsyncEndpoint, Endpoint

logger = logging.getLogger(__name__)

_INSTRUCTIONS = """
Palateful — kitchen management assistant. Use these tools to help the user manage
their recipe collection, shopping lists, meal plans, and pantry.

Conventions:
- Ingredient identifiers are resolved by name automatically — never ask the user for UUIDs
- When a recipe book or shopping list is not specified, the user's default is used
- Import tools are async: they return a job_id; call get_import_status to poll progress
- On error, tools return a human-readable string prefixed with "Error:" (no stack traces)
""".strip()


mcp = FastMCP(
    "Palateful",
    instructions=_INSTRUCTIONS,
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
)


def call_endpoint(endpoint_cls: type[Endpoint], *args: Any, **kwargs: Any) -> str:
    """Run an `Endpoint` subclass with the current MCP request's user/database.

    Returns a JSON-encoded string on success or a human-readable `"Error: ..."`
    message on failure — the format MCP tools are expected to return.
    """
    user = get_current_user()
    database = get_current_database()

    try:
        result = endpoint_cls(database=database, user=user).run(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("MCP endpoint %s raised", endpoint_cls.__name__)
        return f"Error: {exc}"

    if result.get("success"):
        return json.dumps(jsonable_encoder(result.get("data")), default=str)

    return f"Error: {result.get('error_message') or 'Unknown error'}"


async def call_endpoint_async(
    endpoint_cls: type[AsyncEndpoint], *args: Any, **kwargs: Any
) -> str:
    """Async counterpart of `call_endpoint` (aam-3).

    Each Phase 3 domain story swaps its MCP tool file from
    `call_endpoint(...)` to `await call_endpoint_async(...)` at the same
    time as the domain's HTTP handlers convert. The sync helper stays
    until post-cutover so dual-dispatch tools continue to work during
    the observation window.

    Requires an async database — the caller's MCP auth dep must resolve
    to an `AsyncDatabase`, which `get_current_database_async` provides
    (aam-6). Until aam-6 lands, MCP callers keep using the sync helper.
    """
    user = get_current_user()
    database = get_current_database()

    try:
        result = await endpoint_cls(database=database, user=user).run(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("MCP async endpoint %s raised", endpoint_cls.__name__)
        return f"Error: {exc}"

    if result.get("success"):
        return json.dumps(jsonable_encoder(result.get("data")), default=str)

    return f"Error: {result.get('error_message') or 'Unknown error'}"


async def call_agent_tool(tool: BaseTool, **kwargs: Any) -> str:
    """Run a sync agent tool on a worker thread with propagated contextvars.

    Agent tools are sync SQLAlchemy; we run them via asyncio.to_thread wrapped
    in copy_context so the auth contextvars follow across the boundary.
    """
    user = get_current_user()
    database = get_current_database()

    def _invoke() -> str:
        try:
            result = tool.execute(db=database.db, user_id=str(user.id), **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("MCP agent tool %s raised", tool.name)
            return f"Error: {exc}"
        return result.to_message()

    ctx = copy_context()
    return await asyncio.to_thread(ctx.run, _invoke)


def build_mcp_app() -> Starlette:
    """Build the mount-ready ASGI Starlette app wrapping auth + MCP protocol.

    Call this once during FastAPI app startup. The returned Starlette app's
    lifespan must be plumbed into FastAPI's lifespan so the underlying session
    manager starts and stops with the process.
    """
    # Ensure all tools are registered before building the ASGI app.
    from mcp_server.tools import register_all_tools

    register_all_tools()

    inner = mcp.streamable_http_app()

    outer = Starlette(
        routes=[Mount("/", app=inner)],
        middleware=[Middleware(MCPAuthMiddleware)],
        lifespan=lambda _app: mcp.session_manager.run(),
    )
    return outer
