# Story aam-2: AsyncDatabase class + worker contract gate

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 1 — Foundations

## Acceptance Criteria

1. New file `libraries/utils/utils/services/async_database.py` with an `AsyncDatabase` class mirroring the sync `Database` public surface, but every method is `async`.
2. Public methods: `find_by`, `find_or_create_by`, `create`, `create_all`, `update`, `update_all`, `save`, `save_all`, `delete`, `bulk_update`, `find_and_bulk_update`, `where`, `lock`, `close`.
3. `find_or_create_by` uses async `pg_advisory_lock` (via a new `AsyncAdvisoryLock` helper that `await`s `SELECT pg_advisory_lock(:k)` on the async session).
4. `lock()` returns an async context manager.
5. Sync `Database` public API **unchanged** — signature-diff test verifies no surface drift.
6. Worker+parser test suites continue to pass (worker contract gate).
7. Unit-test parity: every sync `Database` behavior gets an async twin where feasible; coverage stays 100%.
8. Lands **dark** — no production handler uses `AsyncDatabase` yet.

## File List

- `libraries/utils/utils/services/async_database.py` (new)
- `libraries/utils/utils/services/async_advisory_lock.py` (new)
- `libraries/utils/tests/test_async_database.py` (new — if utils has a tests dir) OR
- `services/api/tests/test_async_database.py` (new — API test suite since utils has no tests setup)
- `libraries/utils/tests/test_database_api_frozen.py` (new — signature-diff test) OR equivalent placement
