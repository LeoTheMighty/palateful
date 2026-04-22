# QA Walkthrough — sched-2 (IMPORT_FAILED notification)

## Automated regression (passing)

- [x] `services/api/tests/test_import_notifications.py` — 14 tests for
  `_source_label_for_job` branches (url / url_list / spreadsheet /
  unknown) and `notify_import_failed` (hostname title, bulk copy,
  suppression, error swallow).
- [x] `services/api/tests/test_import_failed_transitions.py` — 7 tests
  covering the extract / create `_update_job_counts` transition
  firing, idempotency (no second push on already-failed jobs),
  partial-fail not firing, and cancelled-job guard.

## Manual smoke

Run against staging. Firebase creds must be wired on the worker for
pushes to actually be delivered (otherwise the service is in log-only
mode and the copy is visible in worker logs).

1. **Single bad URL.**
   - Paste a paywalled/broken URL into the import flow (bulk import a
     single URL).
   - Wait for `extract_recipe_task` to run — item ends in `"failed"`.
   - `ImportJob.status` transitions `processing -> failed`.
   - ✅ Expect: one push "🛑 Couldn't import from {hostname}" with body
     "We couldn't extract a recipe. Tap to retry."
   - ✅ Tap → opens `/recipes/import/review-list/{job_id}`.

2. **Full bulk failure.**
   - Paste 3+ unreachable URLs in one bulk import.
   - All items end in `failed`; job transitions to `failed`.
   - ✅ Expect: one push "🛑 Bulk import failed" / "We couldn't extract
     any of the 3 recipes. Tap to retry."

3. **Partial failure does NOT push IMPORT_FAILED.**
   - Mix 1 good URL + 1 bad URL. Good one lands in `awaiting_review`,
     bad in `failed`.
   - Job transitions to `awaiting_review`.
   - ✅ Expect: IMPORT_NEEDS_REVIEW push (existing), NOT IMPORT_FAILED.

4. **Cancelled job.**
   - Start a bulk import, then cancel it before extraction finishes.
   - Kick `_update_job_counts` manually (or let any straggler items
     terminal-fail).
   - ✅ Expect: status stays `cancelled`; no IMPORT_FAILED push.

5. **Post-approval failure (create path).**
   - Import a URL that extracts OK but has malformed data the create
     task rejects (e.g., synthetic test: force an exception in
     `CreateRecipeTask.execute` or use a recipe with zero ingredients).
   - Item status → `failed`.
   - ✅ Expect: IMPORT_FAILED push after final create transition.

6. **Idempotency.**
   - After a job transitions to `failed` and push fires, re-run
     `_update_job_counts` (via re-dispatching the Celery task).
   - ✅ Expect: no second push (previous_status is now `failed`).

7. **Category opt-out.**
   - Toggle `notification_preferences.categories.imports = false`.
   - Trigger any of the above failures.
   - ✅ Expect: `notify_import_failed` fires but `send_to_user` returns
     `suppressed_by_category=true`; device sees no banner.

## Rollback notes

- No DB schema change — rollback = revert the commit.
- Enum value `IMPORT_FAILED` is additive. If a rolled-back backend
  receives a client claiming the notification_type from an in-flight
  push, the Flutter switch will just fall through to `/`, no crash.
- Cancelled-job guard in `_update_job_counts` is a behavior change
  unrelated to the push: confirm no existing flow relied on cancelled
  jobs being re-counted into `completed`.

## Known non-blocking notes

- Pre-existing test failures in `test_fork_recipe.py`, `test_recipe.py`
  (AddRecipeNote), and `test_coverage_gaps.py` are parallel-agent WIP
  (partner-activity epic) and unrelated to sched-2.
