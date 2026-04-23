# aam-6 QA Walkthrough — Async auth deps

**Story**: aam-6-async-auth-deps
**Epic**: epic-api-async-migration

## What changed

- `services/api/src/dependencies.py`:
  - `get_async_database` lifted from yielding `AsyncSession` to yielding
    `AsyncDatabase` (closes the wrapped session on dep teardown).
  - New `get_current_user_async` mirroring the sync `get_current_user`
    flow on the async engine. Same Auth0 verification → user
    find_or_create → finalize_auth → ensure_default_calendar pipeline,
    every DB hop awaited.
  - New `_finalize_auth_async` — async port of `_finalize_auth`.
  - New `_ensure_default_calendar_async` — `async with begin_nested()`
    SAVEPOINT + `IntegrityError` catch on race-loss.
- `services/api/src/mcp_server/auth.py`:
  - New `current_database_async` contextvar.
  - New `get_current_database_async()` accessor (raises 500 if unset).
- `services/api/tests/test_async_engine_dep.py`:
  - Old delegation test replaced — `get_async_database` no longer
    delegates to `get_async_session`; it constructs `AsyncDatabase`
    directly. New test verifies the new shape + close-on-teardown.
  - New `test_get_async_session_raises_when_unconfigured` covering the
    AsyncSessionLocal-is-None branch for the lower-level helper.
- `services/api/tests/test_async_auth_deps.py` (new, 14 tests):
  - `get_current_user_async`: invalid header, valid bearer, E2E bypass,
    E2E onboarding update.
  - `_finalize_auth_async`: fills missing fields, no-op when complete.
  - `_ensure_default_calendar_async`: returns existing fast-path,
    creates when missing, race-loss path (IntegrityError → re-read).
  - 5-way `asyncio.gather` race test on a brand-new auth0_id.
  - WS auth probe through a Starlette WS upgrade dep chain.
  - MCP `get_current_database_async`: contextvar round-trip + raises
    when unset.

## Manual / regression checks

Story lands **dark** — no router uses the new dep. Validation is the
test-suite gate plus targeted assertions on the new behaviors.

- [x] **API full suite green**:
      `DATABASE_URL="postgresql://t:t@t:5432/t" npx nx run api:test`
      → 2453 passed, 100.00% coverage.
- [x] **Utils suite green**:
      `DATABASE_URL="postgresql://t:t@t:5432/t" npx nx run utils:test`
      → 588 passed.
- [x] **Worker contract gate green**:
      `DATABASE_URL="postgresql://t:t@t:5432/t" npx nx run worker:test`
      → 1 passed (smoke).
- [x] **Lint clean**: `npx nx run api:lint` ✓.

## Race-safety verification

- [x] **5-way `asyncio.gather`**: parallel `get_current_user_async`
      invocations for a brand-new `auth0_id` resolve to the SAME
      canonical user — auth flow doesn't fan out into N user rows.
      The actual unique-row guarantee is owned by:
        - `AsyncDatabase.find_or_create_by`'s `pg_advisory_lock` (aam-2)
        - The partial unique index on
          `calendars(owner_id) WHERE is_default = true AND archived_at IS NULL`.
- [x] **Race-loss recovery in `_ensure_default_calendar_async`**: when
      a parallel request wins the INSERT, `IntegrityError` is caught,
      the SAVEPOINT rolls back the inner block, and the second SELECT
      returns the winner's calendar. Confirmed via direct test that
      flushes raise `IntegrityError` and the helper still returns a
      valid calendar reference.

## WebSocket probe

- [x] FastAPI WS dep chain resolves `get_current_user_async` via
      `Depends(...)` exactly like an HTTP dep. The probe wires a
      minimal `@app.websocket(...)` handler with `Depends(get_current_user_async)`,
      overrides `get_async_database` to yield a fake AsyncDatabase,
      mocks the Auth0 verifier, connects via `client.websocket_connect`
      with `Authorization: Bearer ws-token`, and confirms the handler
      receives the resolved user.
- [x] No `MissingGreenlet` or "anyio.ClosedResourceError" surfaced
      during the upgrade — the async dep machinery survives the WS
      transition cleanly.

## Coverage gap fix

The earlier full-suite run reported 99.99% coverage on `dependencies.py`
(line 55: AsyncSessionLocal-is-None branch in `get_async_session`). I
added `test_get_async_session_raises_when_unconfigured` to drive that
branch — final coverage is back at 100.00%.

## Rollback

- Sync `get_current_user` and `_ensure_default_calendar` were not
  modified — every existing handler keeps working unchanged.
- `get_async_database` is not yet used by any router (lands dark);
  reverting just removes the new functions and lifts back to the
  previous AsyncSession-yielding stub.
- `mcp_server/auth.py` additions are pure-additive (contextvar +
  accessor); revert deletes them. No MCP tool consumes them yet.

## Follow-ups

- Phase 3 stories (`aam-10` onward) start consuming `get_current_user_async`
  one domain at a time per the migration runbook.
- `aam-10` (meals) also wires the MCP middleware to populate
  `current_database_async` alongside the sync `current_database` — the
  dep accessor is in place but the contextvar stays `None` until then.
- A future `aam-25` (sync-in-async startup guard) will assert no
  Phase 3 handler imports the sync `get_current_user`.
