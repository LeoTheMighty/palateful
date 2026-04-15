# Story MVP.6: Retry Endpoint + Stage-Aware Dispatch

Status: done

## Story

As a user whose import failed partway through the pipeline,
I want to retry the import from the last stage that succeeded,
so that I don't waste time (and LLM cost) re-running OCR or extraction that already worked.

## Context

With mvp-5 landed, every `ImportItem` now has a `last_successful_stage` column populated by each stage's task on success. This story adds the user-facing retry path that reads that marker and dispatches the *next* stage's task, skipping everything that already succeeded.

Current state:
- `ImportItem.retry_count` exists at `libraries/utils/utils/models/import_item.py:38` but is **incremented on failure only, never checked for re-dispatch**.
- No user-facing retry endpoint exists.
- Tasks are mostly idempotent: `watch_parser_batch_task` is explicitly idempotent (`test_idempotent_on_terminal_batch`), `extract_recipe_task` and `match_ingredients_task` re-read items from DB each call.

**Important risk acknowledgement**: Leo has accepted the risk of concurrent retries racing on the same item (two `create_recipe_task` calls firing at once can create duplicate `Recipe` rows). This story **does not** add a `retry_in_progress` guard. The risk is documented in the epic and in this story's Dev Notes.

## Acceptance Criteria

1. New endpoint `POST /v1/imports/items/{item_id}/retry` exists and requires authentication.
2. The endpoint validates that the item belongs to the requesting user (403 if not).
3. The endpoint validates that the item is in a retryable status (`failed` or — once mvp-5 lands — any status belonging to a job that has been marked failed by the sweeper). Returns 409 with a clear error message if the item is in `pending`, `extracting`, `matching`, `completed`, or `approved`.
4. The endpoint reads `last_successful_stage` and dispatches the next task in the pipeline:
   - `NULL` → dispatch `parse_source_task` with the parent `ImportJob.id` (full restart)
   - `"parsed"` → dispatch `extract_task` with `item_ids=[item.id]`
   - `"extracted"` → dispatch `match_ingredients_task` with `item_id=item.id`
   - `"matched"` → dispatch `create_recipe_task` with `item_id=item.id`
5. Before dispatching, the endpoint resets the item's `status` to match the stage being retried (`pending`, `extracting`, `matching`, or `approved`) and clears `error_message` and `error_code`. `retry_count` is incremented.
6. If the item's parent `ImportJob.status` is `failed`, the endpoint flips it back to `processing` so the UI shows the retry in progress.
7. The endpoint returns 200 with `{"item_id": ..., "dispatched_task": ..., "resumed_from_stage": ...}` so the client can show feedback.
8. **State machine test** — a parametrized test that exercises all four retry-from-stage transitions AND asserts the correct Celery task is dispatched for each. For each transition, one happy-path test and one "retry also fails" test (verifies the item ends up in `failed` state again with `retry_count` incremented a second time).
9. Endpoint-level tests:
   - Auth required (401)
   - Wrong user (403)
   - Non-retryable status (409)
   - Not found (404)
   - Happy path for each stage marker value (200 + correct dispatch)

## Tasks / Subtasks

- [ ] Task 1: Endpoint skeleton (AC: #1, #2, #3)
  - [ ] New file: `services/api/src/api/v1/imports/retry_import_item.py`
  - [ ] Follow the `Endpoint` base class pattern used by other import endpoints (grep `class.*Endpoint` in `services/api/src/api/v1/imports/` for reference)
  - [ ] Define `Params` (path: `item_id: UUID`) and `Response` Pydantic models
  - [ ] Load `ImportItem` with ownership check (via `import_job.user_id`)
  - [ ] Validate status: retryable iff `item.status == "failed"` OR parent job's `status == "failed"` (the sweeper in mvp-5 marks both)
  - [ ] Register the route in the imports router

- [ ] Task 2: Stage-aware dispatch logic (AC: #4, #5, #6)
  - [ ] Implement a pure function `_dispatch_retry(item: ImportItem) -> tuple[str, str]` returning `(task_name, resumed_from_stage_label)` — keep it pure so it's easy to unit test
  - [ ] The function maps `last_successful_stage` → the correct Celery task call, as specified in AC #4
  - [ ] Before dispatch: reset `item.status` to the appropriate "in progress" state for the resumed stage, clear `error_message` and `error_code`, increment `retry_count`, commit
  - [ ] If `item.import_job.status == "failed"`, set it back to `"processing"` and reset `job.error_message = None` before dispatching, then commit
  - [ ] Dispatch the selected task via `.delay()`
  - [ ] Return the dispatched task name and resumed stage label for the response body

- [ ] Task 3: Wire router and OpenAPI (AC: #1, #7)
  - [ ] Add the route to the imports router file (likely `services/api/src/api/v1/imports/router.py` — confirm at implementation)
  - [ ] Ensure the response Pydantic model is referenced so it shows up in OpenAPI docs
  - [ ] Response shape: `{"item_id": str, "dispatched_task": str, "resumed_from_stage": str}` — e.g. `{"item_id": "...", "dispatched_task": "match_ingredients_task", "resumed_from_stage": "extracted"}`

- [ ] Task 4: State machine tests (AC: #8)
  - [ ] New test file: `services/api/test/v1/imports/test_retry_import_item.py` (or matching existing test layout)
  - [ ] Parametrized test covering all 4 stage marker → task dispatch mappings
  - [ ] For each case: set up an `ImportItem` in `failed` state with the given `last_successful_stage`, call the retry endpoint, mock the Celery task, assert the correct task was called with the correct arguments
  - [ ] Also verify `item.status` was reset correctly, `retry_count` incremented, `error_message` cleared, parent job status transitioned from `failed` → `processing`

- [ ] Task 5: Endpoint error-path tests (AC: #9)
  - [ ] Unauth: no token → 401
  - [ ] Wrong user: item owned by user B, request as user A → 403
  - [ ] Non-retryable status: item in `completed`, `matching`, `pending`, `approved` → 409 with descriptive message
  - [ ] Not found: random UUID → 404
  - [ ] Retryable from parent-job-failed state: item in `matching` but parent job is `failed` (sweeper case) → retry succeeds

- [ ] Task 6: Integration with activity feed (optional, leave for mvp-8 if out of scope)
  - [ ] On successful retry dispatch, consider creating a `user_activity` row of type `import_retry_started`. **Skip this unless trivial** — mvp-8 can handle user feedback on the frontend without a backend activity.

## Dev Notes

- **Concurrent retry risk is accepted**: Leo has explicitly okayed the possibility of two tasks racing on the same item. Do NOT add a `retry_in_progress` column or atomic check. If duplicate-recipe corruption shows up in practice, open a follow-up story to add the guard.
- **Why not also handle `status="stuck"` directly?** mvp-5 marks stuck imports as `failed`, not as a new `stuck` status. The retry endpoint therefore only needs to accept `failed`. This keeps the state machine small.
- **Task idempotency**: all downstream tasks are already safe to re-run (confirmed in Round 2 research). `extract_recipe_task` and `match_ingredients_task` re-read items from DB each call. `create_recipe_task` is the only risk — if two run concurrently, two recipes get created. That's the accepted risk.
- **Do not read or write the `retry_count` field as a cap** — it is recorded for debugging/metrics only, not enforced.
- **Stage label strings** (`"parsed"`, `"extracted"`, `"matched"`) must exactly match what mvp-5 writes. If you find yourself typing them in multiple places, extract a module-level constants dict.
- **Do not log the item's `raw_data`** in any error path — OCR text can be long and noisy and pollutes logs. Log `item_id` and `last_successful_stage` only.

### Project Structure Notes

- Import endpoints live under `services/api/src/api/v1/imports/` — confirm at implementation time (the directory name might be `import_items` or similar)
- Pydantic response models should match conventions used by neighboring endpoints (grep an existing `approve_import_item.py` or similar for the exact style)

### References

- `libraries/utils/utils/models/import_item.py:38` (`retry_count`), added `last_successful_stage` from mvp-5
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py` (parse task)
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` (`extract_task`)
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py`
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
- [Story: mvp-5-stage-markers-and-stuck-sweeper.md]
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- `npx nx run api:test` — 1241 passed, 100.00% coverage
- `npx nx run api:lint` — clean

### Completion Notes List

- Refactored dispatch from if/elif chain to a module-level `_STAGE_PLAN` lookup dict for cleaner code and cleaner branch coverage.
- The endpoint does NOT create a `user_activity` row on retry; mvp-8 handles user feedback on the frontend.
- Unknown `last_successful_stage` values fall back to a full restart via `_FULL_RESTART_PLAN`, making the endpoint forward-compatible with future stage markers.
- Job status is only flipped back to `processing` when it was previously `failed` — retry on a failed item whose parent job is still `processing` leaves the job untouched (tested).
- Route is `POST /v1/import-items/{item_id}/retry` (following existing `/import-items` convention), not `/imports/items/{id}/retry` as originally written in the story draft.

### File List

- `services/api/src/api/v1/import_job/retry_import_item.py` (new)
- `services/api/src/api/v1/import_job/__init__.py` (modified)
- `services/api/src/routers/v1/import_router.py` (modified)
- `services/api/tests/test_import.py` (modified — appended `TestRetryImportItem` class with 12 tests)
- `_bmad-output/implementation-artifacts/mvp-6-qa-walkthrough.md` (new)
