# Story MVP.5: Stage Markers + Stuck-Import Sweeper

Status: done

## Story

As Leo dogfooding Palateful,
I want the backend to track the last successfully-completed pipeline stage for each import item and to detect imports that have silently gotten stuck,
so that failed imports can be retried from the point of failure (in mvp-6) and so the "In Progress" section never shows ghost imports that have actually died.

## Context

Today there are two related backend gaps that make the import pipeline feel untrustworthy:

1. **No stage history.** `ImportItem.status` tells us where an item *is* (`extracting`, `matching`, `failed`, …), but loses all history of where it *got to* before failing. A retry endpoint has no way to know whether to restart from parsing, extraction, or matching.

2. **Ghost "processing" imports.** If an import task crashes hard (worker OOM, pod killed, unhandled exception before the except block runs), `ImportJob.status` stays `"processing"` forever. Research confirmed that `_update_job_counts` in `extract_recipe_task.py:255` is the only place that derives a terminal job status, and it only runs when a task's own success/failure path reaches the database. A mid-task crash bypasses it entirely.

This story lays the foundation for everything in the pipeline-recovery theme of the epic:
- Adds a `last_successful_stage` column on `ImportItem` that each task writes after successful completion.
- Adds a periodic Celery beat sweeper that marks stuck `ImportJob`s as `failed`.

This story does **not** add a retry endpoint or any user-facing UI — that is mvp-6 and mvp-8 respectively.

## Acceptance Criteria

1. `ImportItem` has a new column `last_successful_stage: str | None` with an Alembic migration. Allowed values: `"parsed"`, `"extracted"`, `"matched"`, or `NULL`. Default `NULL` for existing rows.
2. `parse_source_task` sets `last_successful_stage = "parsed"` on each `ImportItem` after it is created (or after `_parse_single_url` / `_parse_url_list` completes for that item).
3. `extract_recipe_task._update_item_from_result` sets `last_successful_stage = "extracted"` when moving item status to `"matching"` (success path at `extract_recipe_task.py:173`).
4. `match_ingredients_task` sets `last_successful_stage = "matched"` when moving item status to `"awaiting_review"` or `"approved"` (after line 79-84).
5. A new Celery beat task `sweep_stuck_imports_task` runs every **2 minutes** and:
   - Finds `ImportJob` rows where `status == "processing"` AND `started_at < NOW() - 10 minutes` AND no child `ImportItem.updated_at` has changed in the last 10 minutes.
   - For each such job, sets `job.status = "failed"`, `job.error_message = "Import stalled — no progress for 10 minutes"`, and marks any non-terminal child `ImportItem` rows as `status = "failed"` with `error_message = "Stage stalled"`.
   - Creates a `user_activity` row of type `import_failed` with subtitle "Your import got stuck. Tap to retry."
6. Beat schedule is registered in whatever existing Celery beat config the project uses (grep `beat_schedule` or `celery_beat` to find).
7. Constants `STUCK_IMPORT_JOB_TIMEOUT_MINUTES = 10` and `STUCK_IMPORT_SWEEPER_INTERVAL_SECONDS = 120` are defined in a shared constants location (likely `utils/constants.py`) so they are tunable.
8. Unit tests for the sweeper:
   - Job in `processing` with recent item activity → no change.
   - Job in `processing` with `started_at` > 10min ago AND no item activity in 10min → marked failed, items marked failed, activity row created.
   - Job already in terminal state (`completed`, `failed`, `cancelled`) → ignored.
   - Job in `processing` with `started_at` > 10min ago but one item updated 2min ago → no change (activity threshold not reached).
9. Unit tests verifying each stage task sets `last_successful_stage` correctly on success.

## Tasks / Subtasks

- [ ] Task 1: Schema — add `last_successful_stage` column (AC: #1)
  - [ ] Modify `libraries/utils/utils/models/import_item.py`: add `last_successful_stage: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)`
  - [ ] Generate Alembic migration via `npx nx run migrator:generate` (or whatever the project's migration command is — check `TODO.md` and `docs/DEPLOYMENT.md`)
  - [ ] Migration should be additive only (new nullable column, no backfill needed)
  - [ ] Verify migration is reversible

- [ ] Task 2: Write stage markers in each task (AC: #2, #3, #4)
  - [ ] `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`: after item creation, set `item.last_successful_stage = "parsed"` before commit. For single URL path (`_parse_single_url` line 92-106), set on the new item. For URL list path, bulk-update items belonging to this job.
  - [ ] `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:173`: add `item.last_successful_stage = "extracted"` on the success branch where `item.status = "matching"` is set.
  - [ ] `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py`: locate the success path around lines 79-84 and set `item.last_successful_stage = "matched"` before the commit.
  - [ ] `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py:237-247`: when creating `ImportItem` rows for photo imports, set `last_successful_stage = "parsed"` since the parser stage completed successfully.

- [ ] Task 3: Constants (AC: #7)
  - [ ] Add to `libraries/utils/utils/constants.py` (or existing constants file):
    - `STUCK_IMPORT_JOB_TIMEOUT_MINUTES = 10`
    - `STUCK_IMPORT_SWEEPER_INTERVAL_SECONDS = 120`

- [ ] Task 4: Sweeper task implementation (AC: #5)
  - [ ] New file: `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports_task.py`
  - [ ] Inherits `BaseTask`, registered with Celery as `sweep_stuck_imports_task`
  - [ ] Query: `ImportJob` where `status == "processing"` AND `started_at < now - STUCK_IMPORT_JOB_TIMEOUT_MINUTES`
  - [ ] For each candidate, check child `ImportItem.updated_at` (assumes the column exists — if not, this story must add it as a separate task)
  - [ ] If max `updated_at` across items is also > `STUCK_IMPORT_JOB_TIMEOUT_MINUTES` ago, declare stuck
  - [ ] Update: `job.status = "failed"`, `job.error_message`, mark non-terminal items as `failed`
  - [ ] Create `user_activity` row via `activity_service.create_activity` with `activity_type="import_failed"`
  - [ ] Log each stuck job at `INFO` level with job ID and last-activity timestamp for debugging

- [ ] Task 5: Beat schedule registration (AC: #6)
  - [ ] Locate existing Celery beat config (grep `beat_schedule` or `celery_beat` or `beat_schedule_entries` under `services/worker/` and `libraries/utils/utils/services/celery.py`)
  - [ ] Register `sweep_stuck_imports_task` on a 120-second interval
  - [ ] If no beat config exists, create one in the worker service's startup path. **Check with Leo before spinning up beat infrastructure that doesn't exist.** For now, assume beat exists and is just missing this entry.

- [ ] Task 6: Verify `ImportItem.updated_at` column exists (AC: #5 dependency)
  - [ ] Read `libraries/utils/utils/models/import_item.py` — if `updated_at` doesn't exist, add it as an `onupdate=func.now()` column in the same migration from Task 1 and document in the story File List

- [ ] Task 7: Tests (AC: #8, #9)
  - [ ] New test file: `libraries/utils/test/test_sweep_stuck_imports_task.py` covering the four sweeper scenarios in AC #8
  - [ ] Add test cases to existing extract/match/parse task tests verifying `last_successful_stage` is set correctly — or a single new parametrized test `test_stage_markers_set_on_success` that walks all three transitions
  - [ ] Follow the mocking style used in `libraries/utils/test/test_watch_parser_batch_task.py` (SimpleNamespace fixtures, MagicMock for database, patched Celery dispatch)

## Dev Notes

- **Do not add a `retry_in_progress` column.** Leo has accepted the risk of concurrent retries racing — mvp-6 will not guard against it.
- **Do not build any retry dispatch logic in this story.** Stage markers exist only to be *read* by mvp-6. This story only writes them.
- The sweeper's 10-minute threshold is an arbitrary MVP value. If Leo finds it too aggressive or too lenient in practice, tune the constant.
- **Activity creation**: the sweeper must use the existing `activity_service.create_activity` helper so the dismiss flow in mvp-7 treats sweeper-created activities identically to task-created ones.
- `watch_parser_batch_task.py` is already idempotent (see `test_idempotent_on_terminal_batch`). The sweeper does not need to coordinate with it — if the watcher marks a batch failed after the sweeper already marked the job failed, both terminal states are consistent.
- **Data-layer safety**: the sweeper should use a single transaction per stuck job so the job status, item statuses, and activity row all commit together.
- Keep the sweeper's work bounded: process at most 100 stuck jobs per sweep to avoid long-running beat tasks. If there are more, the next sweep picks them up.

### Project Structure Notes

- New task file lives alongside other import tasks: `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports_task.py`
- Beat schedule config lives in worker startup — confirm exact location at implementation time
- Constants file: grep `libraries/utils/utils/constants.py` — add new constants in the import section if one exists

### References

- `libraries/utils/utils/models/import_item.py` (line 23 for status, line 38 for retry_count)
- `libraries/utils/utils/models/import_job.py` (line 24 for status)
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:173` (stage transition to matching)
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py:79-84` (stage transition to awaiting_review / approved)
- `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py:237-247` (ImportItem creation for photo imports)
- `libraries/utils/utils/services/activity_service.py` (activity creation helper)
- `libraries/utils/test/test_watch_parser_batch_task.py` (mocking style reference)
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- `npx nx run utils:test` — 18 passed
- `npx nx run utils:lint` — clean
- `npx nx run worker:test` — passed
- `npx nx run api:test` — 1229 passed

### Completion Notes List

- Used a single bulk-mark in `parse_source_task._dispatch_extraction_tasks` so all source types (url, url_list, photo, text, spreadsheet) get the `"parsed"` marker through one code path, rather than hunting down every `ImportItem` creation site.
- Photo-path `ImportItem` rows are also marked at creation in `watch_parser_batch_task` as belt-and-suspenders so the marker is correct even if `parse_source_task` short-circuits.
- Sweeper's second gate (`max(child items.updated_at) < cutoff`) prevents false positives when a job is legitimately slow but still making progress.
- Activity creation inside the sweeper is wrapped in try/except so a bad activity insert does not roll back the job status update.
- Pre-existing gap discovered and left out of scope: `match_ingredients_task` failure path does not call `_update_job_counts`. Noted in the QA walkthrough for retrospective tracking.

### File List

- `libraries/utils/utils/constants.py` (modified)
- `libraries/utils/utils/models/import_item.py` (modified)
- `libraries/utils/utils/services/celery.py` (modified)
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py` (modified)
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` (modified)
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py` (modified)
- `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py` (modified)
- `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports_task.py` (new)
- `libraries/utils/test/test_stage_markers.py` (new)
- `libraries/utils/test/test_sweep_stuck_imports_task.py` (new)
- `services/migrator/migrations/versions/20260415000000_add_last_successful_stage.py` (new)
- `_bmad-output/implementation-artifacts/mvp-5-qa-walkthrough.md` (new)
