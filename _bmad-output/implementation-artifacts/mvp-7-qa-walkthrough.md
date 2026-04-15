# QA Walkthrough: MVP.7 — Hard Dismiss Endpoints

## What shipped

1. **`dismissed_at` columns** on both `import_items` and `import_jobs` (timezone-aware datetime, nullable).
2. **Alembic migration** `d1s2m3s4d6e7` — additive, reversible, no backfill.
3. **`POST /v1/import-items/{item_id}/dismiss`** — single-item hard dismiss with ownership gate and status gate. Also flips the parent `ImportJob.dismissed_at` when every sibling item under that job is now dismissed.
4. **`POST /v1/import-jobs/dismiss-all-failed`** — bulk hard-dismiss every failed item owned by the user. Flips jobs whose items are now fully dismissed. Returns `dismissed_count`.
5. **Auto-mark activities as read** — both endpoints update `user_activities` rows whose `metadata_json.import_item_id` matches a dismissed item, setting `read = True`. Dismissing is a stronger action than reading the notification.
6. **List endpoint filter** — `GET /v1/parser/batches` now:
   - Excludes dismissed `ImportJob` rows from the `import_jobs_by_batch` response payload
   - Hides `ParserBatch` rows whose every linked `ImportJob` is dismissed
   - Still shows pre-fan-out batches with zero jobs (running / submitted / pending)
7. **MockImportItem and MockImportJob conftest defaults** updated with `dismissed_at=None`, `last_successful_stage=None`, `retry_count=0`, `error_code=None`, `error_message=None` so existing tests keep passing after schema growth.
8. **Hard dismiss by design**: no soft delete, no 24h trash bin, no backend un-dismiss endpoint. The only undo is a local 4-second snackbar on the frontend (implemented in mvp-8).

## QA checklist

### Automated
- [x] `npx nx run api:test` — **1253 / 1253 pass, 100.00% coverage**
- [x] `npx nx run api:lint` — clean
- [x] `npx nx run utils:test` — 18 / 18 pass (no regressions from the model change)
- [x] `npx nx run utils:lint` — clean

### Manual (to run post-deploy)
- [ ] Run `alembic upgrade head` in staging; verify both `import_items.dismissed_at` and `import_jobs.dismissed_at` columns exist and default NULL
- [ ] Seed a failed import (bad URL); call single-dismiss → verify item + job rows both have `dismissed_at` set, linked user activity is marked `read`
- [ ] Multi-item job: dismiss one item, verify job `dismissed_at` stays NULL; dismiss the other, verify job `dismissed_at` gets set
- [ ] Create 3 failed imports; hit bulk endpoint; verify `dismissed_count=3` and `GET /v1/parser/batches` no longer returns them
- [ ] Regression: a running parser batch with zero ImportJobs yet still shows up on the strip

### Known tradeoffs / follow-ups
- **No index on `dismissed_at IS NULL`**. Today's volume is tiny so planner behavior doesn't matter. Add a partial index if list queries get slow in prod.
- **`dismiss_all_failed` iterates Python-side** rather than doing a single `UPDATE ... WHERE status='failed'`. Same reason: volume is small, Python code is simpler to read. Revisit if it becomes a hot path.
- **Activity auto-read is best-effort**: it runs in the same transaction as the dismissal, but if the JSONB operator is slow we'll see it in dogfood.
- **No admin "un-dismiss" path**. Once dismissed, rows are gone from the UI forever. The row still exists in the DB for manual restore via SQL if needed.

## Files touched

- `libraries/utils/utils/models/import_item.py` (modified — added `dismissed_at`)
- `libraries/utils/utils/models/import_job.py` (modified — added `dismissed_at`)
- `services/migrator/migrations/versions/20260415000001_add_dismissed_at.py` (new)
- `services/api/src/api/v1/import_job/dismiss_import_item.py` (new)
- `services/api/src/api/v1/import_job/dismiss_all_failed_imports.py` (new)
- `services/api/src/api/v1/import_job/__init__.py` (modified — register endpoints)
- `services/api/src/routers/v1/import_router.py` (modified — wire routes)
- `services/api/src/api/v1/parser/list_parser_batches.py` (modified — dismissed filter)
- `services/api/tests/conftest.py` (modified — MockImportJob / MockImportItem defaults)
- `services/api/tests/test_import.py` (modified — TestDismissImportItem + TestDismissAllFailedImports)
- `services/api/tests/test_parser_batches.py` (modified — MockBatchImportJob default + two new list-filter tests)
- `_bmad-output/implementation-artifacts/mvp-7-qa-walkthrough.md` (new)
