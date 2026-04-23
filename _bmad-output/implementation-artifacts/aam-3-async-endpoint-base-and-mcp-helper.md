# Story aam-3: AsyncEndpoint base + MCP call_endpoint_async

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 1 — Foundations

## Acceptance Criteria

1. `utils.api.endpoint.AsyncEndpoint` class alongside `Endpoint`. `async def call`, `async def run`, `async def execute`. Response handling identical.
2. `_log_error_to_db` stays sync; the async path invokes it via `run_in_threadpool` on a **dedicated 3+2 connection sub-pool** (`error_log_engine` / `ErrorLogSessionLocal`) so main-pool exhaustion cannot starve error logging.
3. `services/api/src/mcp_server/server.py::call_endpoint_async` mirrors `call_endpoint`; both coexist until cutover.
4. Unit tests cover happy path, APIException, unhandled exception, invalid shape, threadpool dispatch, exception-swallow for the writer.
5. Lands dark — no subclasses yet. Real subclasses ship per domain in Phase 3.

## File List

- `libraries/utils/utils/api/endpoint.py` (modify — add AsyncEndpoint; sync Endpoint routes error-log writes to the dedicated engine)
- `libraries/utils/utils/services/database.py` (modify — add `error_log_engine` + `ErrorLogSessionLocal`)
- `libraries/utils/test/test_async_endpoint.py` (new)
- `services/api/src/mcp_server/server.py` (modify — add `call_endpoint_async`)
- `services/api/tests/mcp_server/test_server.py` (modify — async call tests)
