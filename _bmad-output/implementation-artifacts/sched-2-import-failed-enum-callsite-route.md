# Story sched-2 — IMPORT_FAILED enum + full-job-failure callsite + Flutter route

**Status:** done
**Epic:** epic-notifications-scheduled-reminders
**Depends on:** nfn-1 (per-category prefs), nfn-2 (copy library). Copy
already landed via sched-1 (`notification_copy.import_failed`).

## Scope

Hook a single push for full-job import failures. Only `extract_recipe_task`
transitions `ImportJob.status` to `"failed"` today (when every item
terminal-failed during extraction). `create_recipe_task` currently only
transitions to `"completed"` — we're extending its `_update_job_counts`
to also detect the all-failed case (when approved items all failed to
create) so post-approval failures surface too. Both fire
`notify_import_failed` exactly once (guarded by a prior-status
transition check).

## File list

- `libraries/utils/utils/services/push_notification.py` [MODIFY] — add `NotificationType.IMPORT_FAILED` + `_CATEGORY_FOR_TYPE` mapping
- `libraries/utils/utils/services/import_notifications.py` [MODIFY] — add `notify_import_failed(database, job)`
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` [MODIFY] — fire push on `awaiting_review | completed | pending | processing -> failed` transition
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` [MODIFY] — detect all-failed case + fire same push
- `app/lib/core/services/push_notification_service.dart` [MODIFY] — `_routeForNotification` case for `import_failed`
- `services/api/tests/test_import_notifications.py` [CREATE] — notify_import_failed + source-label branches
- `services/api/tests/test_import_failed_transitions.py` [CREATE] — extract / create task transition firing + cancelled-job no-op

## Acceptance criteria

- AC1 — `NotificationType.IMPORT_FAILED = "import_failed"` added; mapped to the `imports` category; exhaustiveness assertion still passes.
- AC2 — `notify_import_failed(database, job)`:
  - source_label resolution:
    - `url` → hostname parsed from `job.source_url` (falls back to `"your import"` when parse fails)
    - `url_list` → `"your bulk import"`
    - `spreadsheet` → `job.source_filename` or `"your spreadsheet"`
    - `pdf` / `photo` / `text` / anything else → `"your import"`
  - calls `notification_copy.import_failed(source_label=..., count=job.total_items)`.
  - data payload `{"import_job_id": str(job.id)}`.
  - uses `push_service.send_to_user(user, notification, db.db)` — per-category prefs + quiet hours apply.
  - swallows exceptions; logs via `logger.exception`.
- AC3 — `extract_recipe_task._update_job_counts`: when `previous_status != "failed"` and `job.status == "failed"`, call `notify_import_failed`.
- AC4 — `create_recipe_task._update_job_counts`: when `total_final >= total_items` and `failed_items == total_items`, set `job.status = "failed"` (new branch), and fire `notify_import_failed` on the transition.
- AC5 — Cancelled imports (`job.status == "cancelled"`) never fire IMPORT_FAILED (the terminal-check branches only look at "failed"). Tested explicitly.
- AC6 — Flutter `_routeForNotification` maps `"import_failed"` → `/recipes/import/review-list/{import_job_id}` (same as needs-review/complete).
- AC7 — Tests:
  - `notify_import_failed` title includes hostname for `source_type=url`.
  - `notify_import_failed` title says "Bulk import failed" for `source_type=url_list` with count > 1.
  - `extract_recipe_task` fires on all-items-failed transition.
  - `extract_recipe_task` does NOT fire on re-count while status already `"failed"`.
  - `create_recipe_task` fires when every approved item fails to create.
  - Cancelled job (simulated by setting status to `cancelled` before recount) yields no push.

## Notes

- Hostname truncation already handled inside `notification_copy.import_failed`.
- Call path matches `notify_import_needs_review`: transitions only, exceptions swallowed, Firebase-less environments log-only.
- No migrations; no model changes.

## QA walkthrough

See `sched-2-qa-walkthrough.md`.
