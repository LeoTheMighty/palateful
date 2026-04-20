# Story abi-2a: Backend — delete orphan `import_*` activity writes at source

Status: ready-for-dev

## Story

As the import pipeline,
I want to stop writing `import_*` rows to `user_activities` since the push-dispatch layer reads import_items directly,
so that the badge count and the Notifications tab never disagree with each other because of a parallel write path.

## Acceptance Criteria

1. The following `UserActivity(...)` / `create_activity(...)` calls are deleted (verified against current HEAD — `match_ingredients_task.py` already removed by str-ing-2, so its `import_needs_review` site is a no-op):
   - `services/api/src/api/v1/import_job/start_import.py` — `type="import_started"` — DELETE
   - `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` — `activity_type="import_complete"` — DELETE
   - `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` — `activity_type="import_failed"` — DELETE
   - `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports_task.py` — `activity_type="import_failed"` — DELETE
2. `parser_job_failed` call sites in `watch_parser_job_task.py` and `parser_batch_completion.py` are OUT OF SCOPE — epic targets `import_*` types only.
3. `partner_action` writes in `recipe_book/add_recipe_book_member.py` and `shopping_list/add_item.py` are KEEP (they're the allow-listed type).
4. Pipeline regression: a synthetic import flow start → parser → extractor → matcher writes no `user_activities` row with `type LIKE 'import_%'`. Push dispatch continues to fire for needs-review items (reads `import_items` directly).
5. Existing tests asserting `type="import_started"` / `type="import_complete"` / `type="import_failed"` rows are created from the pipeline are updated to assert the opposite (no such rows are created).

## Key Files

- Modify: `services/api/src/api/v1/import_job/start_import.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
- Modify: `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports_task.py`
- Modify or delete: tests under `services/api/tests/` and `libraries/utils/test/` asserting `import_*` user_activity creation

## Dev Notes

- `match_ingredients_task.py` was deleted entirely by `str-ing-2` (commit `55f70f9`) — the epic's reference to that file is a no-op.
- Pattern for removal: delete the `create_activity(...)` call and its local `from utils.services.activity_service import create_activity` import if this was the only caller in the module.
- Leave push-dispatch code untouched — it reads `import_items` directly in `services/api/src/services/push_notifications.py` (and related tasks).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Completion Notes List

### File List
