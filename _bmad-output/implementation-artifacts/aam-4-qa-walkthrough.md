# aam-4 QA Walkthrough — Async test fixtures + counter parity

**Story**: aam-4-async-test-fixtures-and-counter-parity
**Epic**: epic-api-async-migration

## What changed

- New `libraries/test-helper/test_helper/async_db.py` with three async fixtures:
  `async_postgres_engine` (session-scoped real engine), `async_db_session`
  (AsyncSession with savepoint rollback parity to sync), `async_database`
  (`AsyncDatabase` wrapper).
- `libraries/test-helper/test_helper/conftest.py` re-exports them so any
  service that opts into test_helper picks them up automatically.
- `services/api/tests/conftest.py`:
  - `count_queries` rewritten to additively support BOTH the legacy
    MockDatabase wrap AND a new `before_cursor_execute` listener path on
    `db_engine` + `async_db_engine.sync_engine`. `QueryCounter` public
    surface (`.total / .select / .insert / .update / .delete`) unchanged.
  - New `MockAsyncDatabase` + `_MockAsyncQuery` mirroring the sync mock
    surface with async terminals.
  - New `mock_async_db` fixture and `async_client` fixture (httpx.AsyncClient
    + ASGITransport).
- New `services/api/tests/test_count_queries_back_compat.py` exercising
  every pathway (legacy mock-db, engine listener INSERT/UPDATE/DELETE/SELECT,
  N+1, hybrid, cleanup, `_classify_sql` parametrize).
- New `services/api/tests/test_async_client_fixture.py` exercising the
  async_client end-to-end against `/v1/health` and verifying the dep
  yields the same `mock_async_db` the test holds.

## Manual / regression checks

The story is test-infrastructure-only — no production code changed, no
endpoints converted. Validation is the test-suite gate itself.

- [x] **API full suite green**: `DATABASE_URL="postgresql://t:t@t:5432/t" npx nx run api:test`
      → 2439 passed, 100.00% coverage.
- [x] **Utils suite green**: `DATABASE_URL="postgresql://t:t@t:5432/t" npx nx run utils:test`
      → 588 passed.
- [x] **Worker contract gate green**: `DATABASE_URL="postgresql://t:t@t:5432/t" npx nx run worker:test`
      → 1 passed (smoke).
- [x] **Parser contract gate green**: `npx nx run parser:test`
      → 1 passed.
- [x] **test-helper suite green**: `npx nx run test-helper:test`
      → 1 passed.
- [x] **Lint clean across all touched projects**:
      `npx nx run api:lint` ✓, `npx nx run utils:lint` ✓,
      `npx nx run test-helper:lint` ✓.

## Back-compat verification

- [x] Legacy `count_queries(mock_db)` still increments via mock-db wrap:
      every existing pbq-* test in the suite (test_meal_event,
      test_user_activity, test_shopping_list, test_search,
      test_calendar_router, test_list_meals_filters) passes unchanged.
- [x] New engine-listener path classifies SQL verbs correctly
      (`_classify_sql` parametrized table covers SELECT / INSERT /
      UPDATE / DELETE / WITH / BEGIN / empty / None).
- [x] N+1 scenario test runs N=5 SELECTs in a loop and asserts
      `qc.select >= n` — proves the listener catches per-iteration
      queries.
- [x] Hybrid test using both pathways simultaneously sums into a single
      counter — covers the rare case of a mock-db test that also issues
      a real sync-engine write (e.g. error-log).
- [x] Listener cleanup test confirms a query issued AFTER the block ends
      does NOT increment the prior counter — no listener leakage.

## Fixture surface check

- [x] `async_postgres_engine` skips when `ASYNC_DATABASE_URL` is unset
      (worker/parser image path) — verified via the skip-message format.
- [x] `async_db_session` uses `session.sync_session.after_transaction_end`
      to keep a SAVEPOINT continuously held — production code that calls
      `await session.commit()` inside its scope doesn't break test
      isolation.
- [x] `async_client` fixture overrides BOTH `get_database` (with sync
      `MockDatabase`) and `get_async_database` (with `MockAsyncDatabase`)
      so requests to not-yet-converted sync handlers during the
      dual-dispatch window don't try to instantiate `Database()` against
      the empty test DSN.

## Performance / latency

N/A for this story — no production handlers converted yet. Phase 3
stories will capture before/after deltas via `analyze_latency.py` per
their own QA walkthroughs.

## Rollback

If the rewrite breaks a downstream pbq-* test:
- Revert `services/api/tests/conftest.py` to the prior `count_queries`
  shape (single mock-db pathway) — engine-listener helpers can stay (no
  test depends on them yet); just delete the new test files.
- The async fixtures in `test_helper/async_db.py` are isolated and
  optional; they don't affect any existing test suite.

## Follow-ups

- aam-5 (next story): document the `async_client` + `mock_async_db`
  pattern in the conversion runbook so per-domain story authors don't
  re-derive the override list.
- aam-6: register the demo `async_client` test for the auth dep race
  test scaffolding it adds.
