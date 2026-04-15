# QA Walkthrough: MVP.5 — Stage Markers + Stuck-Import Sweeper

## What shipped

1. **`ImportItem.last_successful_stage` column** — new nullable `String(32)` column. Values: `"parsed" | "extracted" | "matched" | NULL`.
2. **Alembic migration** `c1s2t3a4g5e6` (`20260415000000_add_last_successful_stage.py`) — additive only, reversible.
3. **Stage markers written by four tasks**:
   - `parse_source_task._dispatch_extraction_tasks` → bulk-marks pending items as `"parsed"` before dispatching extraction
   - `watch_parser_batch_task._handle_success` → marks `ImportItem` rows as `"parsed"` at creation time for photo imports
   - `extract_recipe_task._update_item_from_result` → marks as `"extracted"` on the success branch
   - `match_ingredients_task.execute` → marks as `"matched"` on both `approved` and `awaiting_review` branches
4. **`sweep_stuck_imports_task`** — new Celery task that finds `ImportJob` rows where:
   - `status == "processing"` AND `started_at < now - 10min` AND `max(child items.updated_at) < now - 10min`
   Marks them `failed`, marks their non-terminal child items `failed`, creates an `import_failed` `UserActivity` row.
5. **Beat registration** in `celery.py:39` — runs the sweeper every 120 seconds.
6. **Tunable constants** in `utils/constants.py`:
   - `STUCK_IMPORT_JOB_TIMEOUT_MINUTES = 10`
   - `STUCK_IMPORT_SWEEPER_INTERVAL_SECONDS = 120`
   - `STAGE_PARSED`, `STAGE_EXTRACTED`, `STAGE_MATCHED` constants
7. **Test coverage** — two new test files:
   - `test_stage_markers.py` (5 tests): verifies each stage sets the marker on success, and that extract failure does NOT advance the marker.
   - `test_sweep_stuck_imports_task.py` (5 tests): no-candidates, recent-activity keeps job alive, stale job + stale items → marked failed, stale job + no items → marked failed, terminal jobs ignored.

## QA checklist

### Automated
- [x] `npx nx run utils:test` — 18/18 pass (5 new stage marker + 5 new sweeper + existing)
- [x] `npx nx run utils:lint` — clean
- [x] `npx nx run worker:test` — pass (no regressions)
- [x] `npx nx run api:test` — 1229/1229 pass (no regressions)

### Manual (to run post-deploy)
- [ ] Run migration `alembic upgrade head` in staging; confirm `import_items.last_successful_stage` column exists and defaults NULL for existing rows
- [ ] Import a URL recipe end-to-end; confirm `last_successful_stage` progresses NULL → "parsed" → "extracted" → "matched" in the DB
- [ ] Kill the worker mid-extract on a test import; wait 10+ minutes; confirm the sweeper marks the job `failed`, marks the pending item `failed` with `error_code=STUCK_IMPORT`, and creates a user_activity row
- [ ] Confirm Celery beat picks up the new schedule entry on worker startup (grep worker logs for `sweep-stuck-imports`)
- [ ] Confirm the sweeper does NOT touch healthy in-flight imports (import a recipe, watch the sweeper run 2-3 times during extraction without marking it failed)

### Known tradeoffs / follow-ups
- **`match_ingredients_task` failure path** does not call `_update_job_counts` — pre-existing gap, out of scope for mvp-5. Noted here so it shows up in retro.
- **Stage marker on photo path** is set twice (once at `ImportItem` creation in `watch_parser_batch_task`, once again at `parse_source_task._dispatch_extraction_tasks`). The second set is idempotent. Left intentionally as belt-and-suspenders.
- **Sweeper activity creation** is wrapped in try/except so a bad activity insert does not roll back the job status update. The `activity_service.create_activity` helper only flushes (not commits), so it rolls back cleanly if the outer commit fails.

## Files touched

- `libraries/utils/utils/constants.py`
- `libraries/utils/utils/models/import_item.py`
- `libraries/utils/utils/services/celery.py`
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py`
- `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py`
- `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports_task.py` (new)
- `libraries/utils/test/test_stage_markers.py` (new)
- `libraries/utils/test/test_sweep_stuck_imports_task.py` (new)
- `services/migrator/migrations/versions/20260415000000_add_last_successful_stage.py` (new)
