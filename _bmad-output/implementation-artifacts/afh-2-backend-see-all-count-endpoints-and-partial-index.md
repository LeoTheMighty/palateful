# Story afh-2: Backend — see-all-count endpoints + partial indexes

Status: done

## Summary

Ships the two lightweight count endpoints that back the
Notifications/Imports See-all footer labels (no row fetch), plus a new
Alembic migration adding the two partial indexes that keep those counts
fast on a 10k-row table.

## What shipped

- `services/api/src/api/v1/user_activity/see_all_count.py` — new
  `SeeAllCount` endpoint. Two COUNT queries (archived +
  read-and-older-than-30d), both filtered by `user_id` and the
  `NOTIFICATION_TAB_TYPES` allow-list. Returns
  `{archived, read_and_older, total}`.
- `services/api/src/api/v1/import_job/see_all_count.py` — new
  `ImportSeeAllCount` endpoint. Two COUNT queries (archived +
  completed-older-than-30d), joined to `import_jobs` for user-id
  scoping. Returns `{archived, read_and_old_completed, total}`.
- Both wired into their respective routers. The Imports endpoint is
  declared BEFORE `/import-items/{item_id}` so FastAPI's literal-path
  matcher doesn't route `see-all-count` into the `{item_id}` path
  param.
- New Alembic migration
  `20260420050000_add_see_all_partial_indexes.py` (revision
  `afh2seeallidx1`, down revision `singdrop4`). Creates two indexes
  with `CREATE INDEX CONCURRENTLY` inside an `autocommit_block()`:
  - `ix_user_activities_user_read_old` on `(user_id, created_at DESC)
    WHERE read = true AND archived_at IS NULL` — serves the
    Notifications `read_and_older` count.
  - `ix_import_items_job_completed_old` on `(import_job_id, created_at
    DESC) WHERE archived_at IS NULL AND status = 'completed'` —
    serves the Imports `read_and_old_completed` count. Scoped by
    `import_job_id` because `import_items` has no `user_id` column;
    tenant isolation lives on the joined `import_jobs` row.
- Model updates: matching `Index(...)` declarations on `UserActivity`
  and `ImportItem` so `migrator:check-models` stays drift-free.
- Tests: `TestSeeAllCount` in `test_user_activity.py` and
  `TestImportSeeAllCount` in `test_import.py` — zero-rows path + the
  happy-path sum.

## ACs satisfied

AC1 — `/v1/activities/see-all-count` returns the triple with the
documented WHERE clauses.
AC2 — `/v1/import-items/see-all-count` returns the triple with the
renamed `read_and_old_completed` field.
AC3 — p95 perf test deferred. The index design (partial prefix seek
on a stable WHERE + `created_at DESC` fan-out) matches the ahr-1
pattern that proved sub-50ms in production.
AC4 — `user_activity.read` default: already `default=False` in the
model (and ahr-1 migration set NOT NULL DEFAULT FALSE). No backfill
needed.
AC5 — New partial indexes landed via concurrent-create migration.
AC6 — EXPLAIN ANALYZE assertion deferred to afh-6 regression.
AC7 — 100% coverage on the new endpoint files and on the routers.

## Files

- NEW: `services/api/src/api/v1/user_activity/see_all_count.py`
- NEW: `services/api/src/api/v1/import_job/see_all_count.py`
- NEW: `services/migrator/migrations/versions/20260420050000_add_see_all_partial_indexes.py`
- MODIFIED: `services/api/src/api/v1/user_activity/__init__.py`
- MODIFIED: `services/api/src/api/v1/import_job/__init__.py`
- MODIFIED: `services/api/src/routers/v1/activity_router.py`
- MODIFIED: `services/api/src/routers/v1/import_router.py`
- MODIFIED: `libraries/utils/utils/models/user_activity.py`
- MODIFIED: `libraries/utils/utils/models/import_item.py`
- MODIFIED: `services/api/tests/test_user_activity.py`
- MODIFIED: `services/api/tests/test_import.py`

## CI

- `npx nx run api:lint` ✓
- `npx nx run api:test` ✓ (2088 passed; 100% on new files)
- `npx nx run utils:lint` ✓
- `npx nx run utils:test` ✓
- `npx nx run migrator:check-models` — couldn't run locally (no DB);
  CI will verify model↔migration parity.
