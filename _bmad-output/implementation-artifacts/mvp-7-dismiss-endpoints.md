# Story MVP.7: Hard-Dismiss Endpoints for Failed Imports

Status: ready-for-dev

## Story

As a user with failed imports cluttering my Add Recipe screen and import hub,
I want to dismiss individual failed imports and bulk-dismiss all failed imports,
so that I can clear visual noise and move on without staring at ghosts of past failures.

## Context

Today there is no way to make a failed import disappear from the UI without database surgery. The `user_activities` table only supports mark-as-read (`PUT /v1/activities/{id}/read`), not hard delete. `ImportJob` and `ImportItem` rows have no `dismissed_at` or equivalent column.

Leo has chosen **hard dismiss**: dismissal is permanent, there is no 24-hour trash bin, and the only safety net is a 4-second snackbar undo in the frontend (implemented in mvp-8/mvp-9). This keeps the backend simple.

This story adds two endpoints:
- Single-item dismiss: `POST /v1/imports/items/{item_id}/dismiss`
- Bulk dismiss: `POST /v1/imports/dismiss-all-failed`

And adds a `dismissed_at` column on `ImportItem` (and possibly `ImportJob`) so the list-imports endpoints can filter dismissed items out.

## Acceptance Criteria

1. `ImportItem` has a new column `dismissed_at: datetime | None` with an Alembic migration. Default `NULL`.
2. `ImportJob` has a new column `dismissed_at: datetime | None` — set when *all* of a job's items have been dismissed, or when the job is bulk-dismissed directly.
3. New endpoint `POST /v1/imports/items/{item_id}/dismiss`:
   - Requires auth, enforces ownership (403 if not).
   - Only accepts items in `failed` status (or items whose parent job is `failed`). Returns 409 otherwise.
   - Sets `item.dismissed_at = now()`.
   - If after this dismissal every item under the parent `ImportJob` has `dismissed_at` set, also set `job.dismissed_at = now()`.
   - Returns 200 with `{"item_id": str, "dismissed_at": iso_timestamp}`.
4. New endpoint `POST /v1/imports/dismiss-all-failed`:
   - Requires auth.
   - Hard-dismisses **all** failed `ImportItem`s owned by the user (via `import_job.user_id`) that are not already dismissed.
   - Also sets `dismissed_at` on any `ImportJob` whose items are now fully dismissed.
   - Returns 200 with `{"dismissed_count": int}`.
5. Existing list endpoints filter out dismissed records:
   - `GET /v1/parser/batches` (used by `import_batches_strip`) — confirm if this reads `ImportJob` status or `ParserBatch` status; exclude dismissed jobs either way.
   - `GET /v1/imports/jobs` / `GET /v1/imports/items` (whatever feeds the import history screen) — filter on `dismissed_at IS NULL`.
6. Dismissed items and jobs still exist in the database (hard-dismiss = UI hard-delete, not row deletion). This preserves audit history and avoids cascading FK deletes on related rows like `recipes` that may have been partially created.
7. User activities of type `import_failed` linked to a dismissed import item are marked as `read = True` as a side effect of dismissal, so the activity hub also reflects the dismiss.
8. Endpoint tests:
   - Single dismiss happy path (failed item → 200, `dismissed_at` set, job `dismissed_at` set if last item)
   - Single dismiss wrong user → 403
   - Single dismiss wrong status (e.g. `completed`) → 409
   - Single dismiss nonexistent item → 404
   - Bulk dismiss with 3 failed items, 1 already-dismissed, 1 non-failed → `dismissed_count == 3`, untouched items stay untouched
   - Bulk dismiss with zero failed items → 200 `{"dismissed_count": 0}`
9. List endpoint tests verify that dismissed records are excluded from default queries but can be fetched via an explicit `include_dismissed=true` query param if desired (optional — only add the query param if it's trivial).

## Tasks / Subtasks

- [ ] Task 1: Schema changes (AC: #1, #2)
  - [ ] Modify `libraries/utils/utils/models/import_item.py`: add `dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)`
  - [ ] Modify `libraries/utils/utils/models/import_job.py`: same column
  - [ ] Generate Alembic migration (combine with mvp-5's migration if they land at the same time, otherwise a fresh migration)
  - [ ] Add a partial index on `dismissed_at IS NULL` for both tables if query planner needs it — check after implementation whether list queries are slow

- [ ] Task 2: Single-item dismiss endpoint (AC: #3, #7)
  - [ ] New file: `services/api/src/api/v1/imports/dismiss_import_item.py`
  - [ ] Follow the `Endpoint` base class pattern
  - [ ] Validate ownership and retryable-like status (`failed` item OR parent job `failed`)
  - [ ] Set `item.dismissed_at = datetime.now(UTC)`
  - [ ] Check all sibling items under the same `import_job_id`: if all have `dismissed_at IS NOT NULL`, set `job.dismissed_at = now`
  - [ ] Mark any `user_activities` linked to this item via metadata (`import_item_id`) as `read = True`
  - [ ] Commit in one transaction
  - [ ] Return 200 with the dismissed-at timestamp

- [ ] Task 3: Bulk-dismiss-all-failed endpoint (AC: #4, #7)
  - [ ] New file: `services/api/src/api/v1/imports/dismiss_all_failed_imports.py`
  - [ ] Single query: `UPDATE import_items SET dismissed_at = now() WHERE import_job_id IN (SELECT id FROM import_jobs WHERE user_id = :user_id) AND status = 'failed' AND dismissed_at IS NULL` (or ORM equivalent)
  - [ ] Count rows affected for the response
  - [ ] Second query: set `job.dismissed_at` on any job whose items are now fully dismissed (can be a correlated subquery or a Python-level iteration — pick whichever is cleanest)
  - [ ] Mark corresponding `user_activities` as read in the same transaction
  - [ ] Return 200 with `{"dismissed_count": n}`

- [ ] Task 4: Filter dismissed records from list endpoints (AC: #5)
  - [ ] `services/api/src/api/v1/parser/list_parser_batches.py:10`: add filter to exclude `ImportJob` rows with `dismissed_at IS NOT NULL` (and/or `ParserBatch` rows whose linked jobs are dismissed — trace the join)
  - [ ] Grep for any other endpoint that lists `ImportJob` or `ImportItem` rows: add the same filter
  - [ ] Optionally accept an `include_dismissed: bool = False` query param for debugging / admin views — skip if it adds complexity

- [ ] Task 5: Router registration (AC: #3, #4)
  - [ ] Add both routes to the imports router
  - [ ] Verify OpenAPI shows the new routes

- [ ] Task 6: Tests (AC: #8, #9)
  - [ ] `services/api/test/v1/imports/test_dismiss_import_item.py`: single-dismiss happy, wrong user, wrong status, not found, last-item-triggers-job-dismiss
  - [ ] `services/api/test/v1/imports/test_dismiss_all_failed_imports.py`: bulk happy, mixed set, zero-failures case
  - [ ] Update `test_list_parser_batches.py` (if it exists) to verify dismissed records are excluded

## Dev Notes

- **Hard dismiss, no trash bin**: `dismissed_at` is the only marker. There is no UI path to un-dismiss. The snackbar undo in mvp-8/mvp-9 is implemented by the Flutter client caching the last dismissed item and calling an un-dismiss endpoint — decide in mvp-8 whether that endpoint exists or whether the snackbar just preserves local UI state for 4 seconds and there is no backend undo at all. **Recommendation**: skip the backend un-dismiss endpoint; snackbar undo keeps local state only. If the user waits >4s before undoing, the backend has already committed the dismissal and the row is gone from list queries.
- **Do not delete rows**. Dismissal is a UI-level hide, not a DB-level delete. This preserves debug-ability and avoids FK cascade cliffs.
- **Activities auto-mark-read**: dismissing the import is a stronger action than reading the notification, so reading comes for free. Do not add a separate "mark activity read" call path.
- **Bulk endpoint scope**: "dismiss all failed" means failed items owned by the user. It does NOT touch failed items on shared recipe books if the user is not the owner. Verify the ownership check before implementing.
- **Transaction safety**: the bulk endpoint may touch many rows. Use a single `UPDATE ... WHERE` statement rather than loading rows into Python and iterating. If the helper `database.db.execute` is the right tool, use it.

### Project Structure Notes

- Endpoints live under `services/api/src/api/v1/imports/`
- Router file: `services/api/src/api/v1/imports/router.py` (confirm)
- Test directory: `services/api/test/v1/imports/` (mirrors src layout)

### References

- `libraries/utils/utils/models/import_item.py` (target for new column)
- `libraries/utils/utils/models/import_job.py` (target for new column)
- `libraries/utils/utils/models/user_activity.py` (the `read` field for auto-mark)
- `services/api/src/api/v1/parser/list_parser_batches.py:10` (filter site)
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
