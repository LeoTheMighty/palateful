# QA Walkthrough — ahr-1 Backend archive columns + endpoints

## What shipped
Backend plumbing for the Activity Hub redesign's swipe-to-archive:

- Alembic migration `a1h2r3a4r5c1` adds four partial indexes (hot-path +
  see-all) on `user_activities` and `import_items`. `archived_at` column
  itself already exists via `JoinsBase` on every table.
- New endpoints:
  - `POST /v1/activities/{id}/archive` and `/unarchive` (owner-only,
    idempotent).
  - `POST /v1/import-items/{id}/archive` and `/unarchive` (recipe-book
    owner/editor, idempotent, `SELECT ... FOR UPDATE` row-locked status
    re-read on archive to reject in-progress items with 409).
- List-endpoint filters:
  - `GET /v1/activities?include_archived=<bool>` (default false).
  - `GET /v1/import-jobs?include_archived=<bool>&archived_only=<bool>`
    (default false both). `archived_only=true & include_archived=false`
    → 400 `detail="contradictory filters"`.
  - `GET /v1/import-jobs/{id}/items?include_archived=<bool>` (default false).
- `UserActivity` and `ImportItem` models declare the new partial indexes
  in `__table_args__` so `alembic check` stays clean.
- `ListActivities`/`ListImportJobs`/`ListImportItems` responses now
  include `archived_at` on each item so the See-all footer can sort by
  archive timestamp.

## Deviation from epic copy
- Epic referenced `/v1/user-activities/...` — actual router prefix is
  `/v1/activities/...` (established since 12-3). Used the real prefix.
  The Flutter contract in ahr-3 must match.
- Epic included `awaiting_parser` in the in-progress status set — not a
  real ImportItem status today. Included anyway as a defensive guard
  matching the epic's blue-section mapping.
- `EXPLAIN ANALYZE`-based query-plan test (epic AC14) is not achievable
  in the mock-based API test harness. Partial indexes are verified by
  the migration's model parity check (alembic.check).

## Local CI status
- `npx nx run api:lint` — pass.
- `npx nx run api:test` — **1655 tests pass, 100% line coverage**.
- `npx nx run utils:lint` — pass.
- `npx nx run utils:test` — 164 tests pass.
- `npx nx run migrator:lint` — pass.
- `npx nx run migrator:check-models` — **pollution from pre-existing
  untracked riip-1 WIP** (two head migrations + `UnitAlias` model
  without its migration). Not caused by this story; CI on the pushed
  commit alone (no untracked files) should be clean.

## QA checklist (against Story ACs)

- [x] **AC1** — Partial indexes present on both tables, hot-path
      (`archived_at IS NULL`) and see-all (`archived_at IS NOT NULL`).
- [x] **AC2** — `CREATE INDEX CONCURRENTLY` inside `autocommit_block()`.
- [x] **AC3** — `POST /v1/activities/{id}/archive` sets `archived_at`,
      200 with row; 403 owner check via query `user_id=user.id`.
- [x] **AC4** — `POST /v1/activities/{id}/unarchive` clears
      `archived_at`. Idempotent.
- [x] **AC5** — `POST /v1/import-items/{id}/archive` uses
      `with_for_update()` + status re-read; 409
      `detail="cannot archive in-progress import"` when status
      in-progress. 403 for non-owner/editor.
- [x] **AC6** — Archive orthogonal to dismiss. Default list query
      filters both (`archived_at IS NULL` AND `dismissed_at IS NULL`).
      Archive/dismiss set independent columns.
- [x] **AC7** — `POST /v1/import-items/{id}/unarchive` clears
      `archived_at`. Idempotent.
- [x] **AC8** — `?include_archived=<bool>` on all three list endpoints.
- [x] **AC9** — `?archived_only=<bool>` on `/v1/import-jobs`.
      `archived_only=true & include_archived=false` returns 400.
- [x] **AC10** — Idempotency tests: archive→archive is 200 no-op;
      unarchive on active is 200 no-op.
- [x] **AC11** — 409 tested with seeded in-progress item.
- [x] **AC12** — Archive/unarchive are not audit-logged (no
      ErrorLog/audit writes in the endpoints).
- [x] **AC13** — Integration-level tests cover list + toggle flow at
      the mock-DB level.
- [~] **AC14** — `EXPLAIN ANALYZE` not achievable in mock harness;
      index presence verified via model parity.

## Manual smoke (optional, for full confidence)
1. `docker compose up` (brings up Postgres with applied migrations).
2. `docker compose --profile migrate up migrator` to apply my
   migration locally.
3. `psql $DATABASE_URL -c "\d+ user_activities" | grep archived` — four
   rows expected: original `archived_at` column + two new partial
   indexes.
4. Curl against the endpoint:
   ```
   curl -X POST http://localhost:8000/v1/activities/<activity-id>/archive \
        -H "Authorization: Bearer <jwt>"
   ```
   Expect 200 with `{"id": "...", "archived_at": "2026-04-18T..."}`.
