# Story aam-6: Async auth deps

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 1 — Foundations

## Acceptance Criteria

1. `services/api/src/dependencies.py` adds `async def get_current_user_async(authorization, database = Depends(get_async_database)) -> User`.
2. Calls `await database.find_or_create_by(User, auth0_id=..., defaults=...)`.
3. `_finalize_auth_async(database, user, claims)` implemented — same field-sync logic as the sync version, awaits `database.update(...)`.
4. `_ensure_default_calendar_async(database, user)` uses `async with database.db.begin_nested()` + `IntegrityError` catch — preserves the race-safety contract via the partial unique index on `calendars(owner_id) WHERE is_default = true AND archived_at IS NULL`.
5. `services/api/src/mcp_server/auth.py` gains `get_current_database_async` alongside the existing sync `get_current_database`. Backed by a new `current_database_async` contextvar.
6. `get_async_database` lifted from the aam-1 stub (which yielded `AsyncSession`) to yield an `AsyncDatabase` wrapper — single source of truth for the async DB dep.
7. Sync `get_current_user` and friends untouched; no router switches deps yet.
8. **Race test** (`test_get_current_user_async_5way_race_creates_one_user_one_calendar`): 5 parallel `asyncio.gather` invocations for a brand-new auth0_id resolve to the same canonical user; auth flow doesn't fan out into N user rows.
9. **WebSocket auth probe** (`test_get_current_user_async_ws_upgrade_dep_chain`): `get_current_user_async` resolves cleanly inside a Starlette WS upgrade dep chain — confirms FastAPI's WS dep machinery handles the async dep correctly.
10. Lands **dark** — no router uses the async dep yet. Phase 3 stories flip routers domain by domain.

## File List

- `services/api/src/dependencies.py` (modify — `get_async_database` lifted to yield `AsyncDatabase`; new `get_current_user_async`, `_finalize_auth_async`, `_ensure_default_calendar_async`)
- `services/api/src/mcp_server/auth.py` (modify — add `current_database_async` contextvar + `get_current_database_async`)
- `services/api/tests/test_async_engine_dep.py` (modify — replace the obsolete delegation test with one verifying `get_async_database` now yields `AsyncDatabase` and closes the wrapped session; add `test_get_async_session_raises_when_unconfigured` for the unset-sessionmaker branch)
- `services/api/tests/test_async_auth_deps.py` (new — covers `get_current_user_async`, `_finalize_auth_async`, `_ensure_default_calendar_async` (existing/create/race-loss), 5-way race test, WS auth probe, MCP `get_current_database_async`)

## Notes

- `_ensure_default_calendar_async` mirrors the sync version line-for-line: probe, `async with begin_nested()` SAVEPOINT for the INSERT, `IntegrityError` catch + re-read on race-loss. Async port is mechanical — no behavior changes.
- `get_async_database` returning an `AsyncDatabase` (not bare `AsyncSession`) is the type Phase 3 stories will depend on. The aam-1 stub's `yield session` was always a temporary contract; aam-6 makes it real.
- `current_database_async` contextvar is added but no MCP middleware path populates it yet — that lands in the first MCP-tool conversion story (alongside `meals.py` MCP tools in `aam-10`). The dep is in place so `aam-10`'s test scaffolding doesn't have to add it concurrently.
- WS auth probe asserts only that the upgrade succeeds + the dep yields the expected user. Real per-domain WS handlers (`recipe_book_router`, `shopping_list_router`) get explicit reconnect-burst tests in their own Phase 3 stories (`aam-11`, `aam-13`).
