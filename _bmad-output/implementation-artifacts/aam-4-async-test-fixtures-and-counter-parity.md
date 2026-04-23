# Story aam-4: Async test fixtures + counter parity

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 1 — Foundations

## Acceptance Criteria

1. `libraries/test_helper/async_db.py` provides `async_postgres_engine` (session-scoped) + `async_db_session` (AsyncSession with savepoint nested-tx rollback) + `async_database` (`AsyncDatabase` wrapper) fixtures.
2. `libraries/test_helper/conftest.py` re-exports the async fixtures so any service that opts into test_helper picks them up automatically.
3. `services/api/tests/conftest.py` adds `async_client` fixture (httpx.AsyncClient + ASGITransport against the FastAPI app) plus `MockAsyncDatabase` and the matching `mock_async_db` fixture.
4. `count_queries` rewritten as polymorphic: it still wraps a `MockDatabase` (legacy `pbq-*` tests pass `count_queries(mock_db)` exactly as before), AND it additively attaches `before_cursor_execute` listeners on `db_engine` and `async_db_engine.sync_engine` when those engines exist.
5. `QueryCounter` public surface unchanged: `.total / .select / .insert / .update / .delete / .query_args / .query_count_for(model)` — every existing pbq-* assertion keeps running without edit.
6. Back-compat regression test (`test_count_queries_back_compat.py`) covers (a) sync mock-db pathway, (b) engine-listener pathway with INSERT/UPDATE/DELETE/SELECT classification, (c) N+1 scenario showing counter ≥ N, (d) hybrid pathway summing both, plus listener-cleanup-after-block guarantee.
7. Demo test (`test_async_client_fixture.py`) exercises the `async_client` fixture end-to-end against `/v1/health` and confirms the `mock_async_db` instance is the same one the dep yields.
8. Worker + parser smoke suites continue to pass (worker contract gate). Full API suite (2439 tests) stays green at 100% coverage.

## File List

- `libraries/test-helper/test_helper/async_db.py` (new)
- `libraries/test-helper/test_helper/conftest.py` (modify — re-export async fixtures)
- `services/api/tests/conftest.py` (modify — `_classify_sql`, `_attach_engine_listeners`, polymorphic `count_queries`, `MockAsyncDatabase`, `_MockAsyncQuery`, `mock_async_db`, `async_client`)
- `services/api/tests/test_count_queries_back_compat.py` (new)
- `services/api/tests/test_async_client_fixture.py` (new)

## Notes

- Async fixture is conditional on `ASYNC_DATABASE_URL`; when unset (worker/parser image), `async_postgres_engine` skips with an explicit message rather than crashing inside SQLAlchemy.
- `count_queries` rewrite is **additive**: the engine-listener branch is independent of the mock-db branch. Existing tests with `count_queries(mock_db)` keep working unchanged because the engines are `None` in the API test env (DATABASE_URL is `""`).
- `async_client` fixture overrides BOTH `get_database` (with sync `MockDatabase`) and `get_async_database` (with `MockAsyncDatabase`) so a request that lands on a not-yet-converted handler during the dual-dispatch window doesn't try to instantiate `Database()` and fail on the empty test DSN.
- `MockAsyncDatabase.where()` returns an `_MockAsyncQuery` whose terminals are `await`able — mirrors `AsyncDatabase.where → AsyncQuery` semantics so per-domain test conversion is mostly s/`def`/`async def`/.
- No changes to sync `Database` public API, no changes to existing `client` / `db_session` / `database` fixtures — worker contract gate satisfied (worker + parser smoke tests green).
