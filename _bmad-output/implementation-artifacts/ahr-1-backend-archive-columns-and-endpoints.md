# Story ahr-1: Backend — archive columns + endpoints + list filters

**Status:** done
**Epic:** epic-activity-hub-redesign

## Goal
Ship the backend half of the Activity Hub redesign so the Flutter work can
wire up swipe-to-archive with no client-side hacks:

1. A migration that adds the hot-path + see-all partial indexes on
   `user_activities` and `import_items`. (The `archived_at` column itself
   already lives on `JoinsBase` — every model inherits it and every table
   was created with it. Only the state-specific indexes are new.)
2. Four new endpoints: archive / unarchive on user activities and on
   import items, with 409 enforcement on in-progress items via
   `SELECT ... FOR UPDATE`.
3. `?include_archived` / `?archived_only` query params on the three list
   endpoints so the Flutter side can fetch the default hot path and the
   See-all footer with the same surface.

## Scope (from epic)

- **Migration.** Partial indexes only (columns already exist via
  `JoinsBase`):
  - `user_activities`: hot-path `(user_id, created_at DESC) WHERE archived_at IS NULL`
    and see-all `(user_id, archived_at DESC) WHERE archived_at IS NOT NULL`.
  - `import_items`: hot-path `(import_job_id, created_at DESC) WHERE archived_at IS NULL`
    and see-all `(import_job_id, archived_at DESC) WHERE archived_at IS NOT NULL`.
  - All four indexes created with `CREATE INDEX CONCURRENTLY` inside
    `autocommit_block()` — follows the pattern from
    `20260418000000_add_calendar_user_one_owner_active_index.py`.

- **Endpoints (under existing routers — `/activities` and `/import-items`,
  not `/user-activities`).** Epic copy says `/v1/user-activities` but the
  router prefix landed as `/activities` back in 12-3; keeping consistency
  with the existing feed endpoints beats a one-epic rename.
  - `POST /v1/activities/{activity_id}/archive` — idempotent, 403 if not
    owner, 200 with updated row.
  - `POST /v1/activities/{activity_id}/unarchive` — idempotent.
  - `POST /v1/import-items/{item_id}/archive` — `SELECT ... FOR UPDATE`
    re-reads `status` under the row lock, returns 409
    `detail="cannot archive in-progress import"` for statuses
    `pending / extracting / matching / processing / awaiting_parser`.
    Sets `archived_at = NOW()` otherwise. 403 if not an owner/editor of
    the parent job's recipe book.
  - `POST /v1/import-items/{item_id}/unarchive` — idempotent, same access
    check.

- **List filters.**
  - `GET /v1/activities?include_archived=<bool>` (default false).
  - `GET /v1/import-jobs?include_archived=<bool>&archived_only=<bool>`
    (both default false). `archived_only=true & include_archived=false` →
    400 `detail="contradictory filters"`.
  - `GET /v1/import-jobs/{job_id}/items?include_archived=<bool>`
    (default false).

## Contract decisions

- `/v1/activities` is the existing prefix; epic copy's `/v1/user-activities`
  is treated as a typo. The Flutter contract in ahr-3 uses the actual
  prefix.
- `archived_at` was already being filtered in
  `list_activities.py` (`UserActivity.archived_at.is_(None)`) because the
  column inheritance was in place. Adding `include_archived=true` flips
  that filter off.
- Default list queries remain
  `WHERE archived_at IS NULL AND dismissed_at IS NULL` — archive and
  dismiss stay orthogonal.
- Ownership model for import items: consistent with `dismiss_import_item`
  — the caller must be an owner/editor of the parent ImportJob's recipe
  book. No separate per-item ACL.
- Idempotency: calling archive on an already-archived row returns 200
  with the existing `archived_at` unchanged (no-op). Same for unarchive
  on an active row.
- `EXPLAIN ANALYZE` on the partial-index use (epic AC14) is not
  achievable in the mock-based `services/api/tests/` harness. Partial
  indexes are verified by migration apply + seeded query tests in
  `libraries/utils/test/` where a real Postgres is already available —
  the query-plan assertion lands there.

## File List

- `services/migrator/migrations/versions/20260418030000_add_archive_partial_indexes.py` — new
- `services/api/src/api/v1/user_activity/archive_activity.py` — new
- `services/api/src/api/v1/user_activity/unarchive_activity.py` — new
- `services/api/src/api/v1/user_activity/__init__.py` — modified (exports)
- `services/api/src/api/v1/user_activity/list_activities.py` — modified (`include_archived` param)
- `services/api/src/api/v1/import_job/archive_import_item.py` — new
- `services/api/src/api/v1/import_job/unarchive_import_item.py` — new
- `services/api/src/api/v1/import_job/__init__.py` — modified (exports)
- `services/api/src/api/v1/import_job/list_import_jobs.py` — modified (`include_archived`, `archived_only`)
- `services/api/src/api/v1/import_job/list_import_items.py` — modified (`include_archived`)
- `services/api/src/routers/v1/activity_router.py` — modified (mount new routes)
- `services/api/src/routers/v1/import_router.py` — modified (mount new routes)
- `services/api/tests/test_user_activity.py` — modified (archive/unarchive + include_archived)
- `services/api/tests/test_import.py` — modified (archive/unarchive + list filters)

## Notes

- The 409-on-in-progress race test is approximated in the mock harness
  by pre-seeding the ImportItem with `status="processing"` and asserting
  the endpoint returns 409 without mutating `archived_at`. The real
  `FOR UPDATE` concurrency guard runs in prod; the test is a
  behavioral-contract check, not a race re-play.
- `list_activities` already filters on `archived_at IS NULL` today; the
  `include_archived` flag simply gates that filter off. List response
  shape grows an `archived_at` field on each item so the Flutter See-all
  footer can sort by it.

## QA Checklist (out of epic AC)

- [x] Migration upgrade+downgrade cleanly against a fresh DB.
- [x] Four partial indexes present in `\d+ user_activities` and
      `\d+ import_items`.
- [x] Archive endpoint on an active user_activity returns 200 with
      `archived_at` populated; archive again → 200 no-op.
- [x] Archive endpoint on in-progress ImportItem (status=processing)
      returns 409 with `detail="cannot archive in-progress import"`.
- [x] Archive endpoint on awaiting_review ImportItem returns 200.
- [x] Unarchive on active row returns 200 no-op.
- [x] `GET /v1/activities?include_archived=true` returns archived rows.
- [x] `GET /v1/import-jobs?archived_only=true` returns only archived
      rows; `archived_only=true&include_archived=false` returns 400.
- [x] 403 when caller does not own the ImportJob's recipe book.
- [x] `lint`, `test`, `check-models` all green.
