# Story MCP.1: MCP Infrastructure — Server, Auth, Mount

Status: ready-for-dev

## Story

As a developer,
I want a working MCP server mounted on the FastAPI app with JWT authentication,
so that MCP clients (Claude Desktop, Claude Code) can connect and call tools securely.

## Acceptance Criteria

1. `mcp[cli]>=1.9` confirmed in the api service dependency graph (already transitively installed; ensure direct dep recorded so we can rely on it)
2. `FastMCP` server instance created with name "Palateful" and helpful instructions string
3. Auth middleware extracts Bearer JWT from Authorization header, verifies via `Auth0Verifier`, stores authenticated `User` and `Database` in Python `contextvars`
4. Auth middleware returns 401 JSON response for missing/invalid/expired tokens
5. MCP ASGI app mounted at `/mcp` in `services/api/src/main.py` — existing `/v1/*` routes unaffected
6. A test `get_profile` tool returns the authenticated user's name, email, and default recipe book
7. Standardized `call_endpoint()` helper wraps any `Endpoint` subclass: instantiates with user/database, calls `.run()`, returns JSON string on success or error message on failure
8. `contextvars` propagation works correctly when tools use `asyncio.to_thread()` via `copy_context().run()`

## Technical Approach

**Package naming deviation:** The epic specifies `services/api/src/mcp/` but the installed `mcp` Python SDK lives at top-level `mcp`. With `PYTHONPATH=src`, a local `mcp/` directory would shadow the SDK. Using `services/api/src/mcp_server/` instead — functionally equivalent, avoids Python import conflicts.

- Use `FastMCP` from `mcp.server.fastmcp` for tool definitions via `@mcp.tool()` decorators
- `FastMCP.streamable_http_app()` returns the Starlette ASGI app with lifespan for the session manager
- Mount at `/mcp` via `app.mount()` with streamable_http_path="/" on FastMCP so routes land at `/mcp` (not `/mcp/mcp`)
- Nest the MCP session manager's lifespan into FastAPI's lifespan so the manager runs for the app lifetime
- Auth middleware is a Starlette middleware wrapping the MCP ASGI app — intercepts before MCP protocol processes
- Reuse `utils.services.auth0.get_auth0_verifier` for JWT verification
- Reuse `utils.services.database.Database` for DB session management
- E2E test bypass: accept `e2e-test-token` when settings.e2e_test_mode is true (same pattern as `dependencies.py`)

## File List

- Create: `services/api/src/mcp_server/__init__.py`
- Create: `services/api/src/mcp_server/server.py` (FastMCP instance, call_endpoint helper, app factory)
- Create: `services/api/src/mcp_server/auth.py` (Starlette middleware, contextvars, 401 handling)
- Create: `services/api/src/mcp_server/tools/__init__.py` (registers all tools)
- Create: `services/api/src/mcp_server/tools/user.py` (get_profile test tool)
- Modify: `services/api/src/main.py` (mount MCP app with lifespan)
- Modify: `services/api/pyproject.toml` (add direct mcp dep)
- Create: `services/api/tests/mcp/__init__.py`
- Create: `services/api/tests/mcp/test_auth.py`
- Create: `services/api/tests/mcp/test_server.py`

## Dev Agent Record

### Completion Notes

TBD
