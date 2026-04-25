# import-dup-2 — Backend: skip endpoint + `skipped` status

**Epic:** `epic-import-duplicate-detection`
**Status:** review
**Order in epic:** 2 of 4 (powers the banner's primary action; story 3 calls it from Flutter)

## Why

The Approve-Import banner's **Skip** button needs a backend endpoint
to drop the parsed import without creating a recipe. The `skipped`
state preserves the parsed payload so the user can recover from
import-activity history if Skip turns out to be wrong.

This story is mostly a **validation story** — the endpoint already
exists (`POST /v1/import-items/{id}/skip` was wired up during
`epic-3-recipe-import-pipeline`). The one behaviour change required by
the epic is **idempotency**: skipping an already-skipped item should
be a 200 no-op, not a 400. The existing implementation returned 400.

## Scope — files this story touches

**MODIFY**
- `services/api/src/api/v1/import_job/skip_import_item.py` — split
  the prior `if status in ("completed","skipped")` guard into two
  branches: `status == "skipped"` returns 200 with current state;
  `status == "completed"` keeps the 400 (can't unwind an already-
  imported recipe via skip — the user wants `archive` on the resulting
  recipe instead).
- `services/api/tests/test_import.py` — rename
  `test_skip_import_item_already_skipped` to
  `test_skip_import_item_already_skipped_is_idempotent`, flip its
  assertion to 200, and add an assertion that `_update_job_counts`
  is NOT called on the no-op path (so repeated taps don't thrash the
  job's totals).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  `import-dup-2-...: backlog → done`.

**NEW**
- `_bmad-output/implementation-artifacts/import-dup-2-backend-skip-endpoint-and-skipped-status.md`
  (this file).
- `_bmad-output/implementation-artifacts/import-dup-2-backend-skip-endpoint-and-skipped-status-qa-walkthrough.md`
  (QA checklist).

## Acceptance criteria (from the epic)

- [x] **New enum value `ImportItemStatus.skipped`** — the column is a
  `String(20)` (not a DB enum), and `skipped` is documented in the
  model docstring + already in active use across the import pipeline
  (see `list_import_items.py`, `_update_job_counts`). No Alembic
  migration is required because the column type is unchanged. AC
  satisfied without a migration.
- [x] **`POST /v1/import-items/{id}/skip` endpoint sets status to
  `skipped`, returns the updated item** — endpoint exists and was
  fully tested by the prior story (`test_skip_import_item_pending_status`
  + 7 friends). No change.
- [x] **Authorization: only the import item's owner can skip; 403
  otherwise** — covered by `test_skip_import_item_no_membership` and
  `test_skip_import_item_viewer_role`. No change.
- [x] **Idempotent: skipping an already-skipped item is a no-op
  (200 with current state)** — fixed in this story. New test
  `test_skip_import_item_already_skipped_is_idempotent` asserts the
  200 + no-op semantics.
- [x] **mutationBus event** — backend has no mutationBus
  (frontend-only abstraction per `app/lib/core/state/README.md`). The
  event is emitted by the Flutter `ImportItemService.skipImportItem`
  call site in story 3, not by the backend. AC satisfied at the
  frontend layer.
- [x] **100% line coverage maintained** — `nx run api:test` reports
  100.00% with 2541 tests passing.

## Implementation notes

### Why the prior 400-on-already-skipped was wrong

The Approve-Import banner is a single screen with three buttons (Skip,
Restore, Add anyway). On a flaky cellular connection, the user can:
1. Tap Skip → the request goes out
2. The spinner stays up while the network takes 4s
3. The user retaps Skip → second request sent
4. First request lands → status flips to skipped
5. Second request lands → server saw `status == skipped` and 400'd

That 400 surfaces as an error toast even though *the user's intent
was already honored*. Idempotent semantics avoid this entirely: both
requests succeed, both return the same final state.

This is the same reasoning that makes archive / unarchive endpoints
idempotent throughout the codebase — a button that can be tapped
twice should be safe to tap twice.

### Why `completed` still 400's

A `completed` import item has a `created_recipe_id` pointing at a
real Recipe row. "Skipping" a completed import would be ambiguous —
does it delete the recipe, archive it, leave it alone? The right
correction surface is `POST /v1/recipes/{recipe_id}/archive` on the
created recipe. Leaving the 400 makes that affordance discoverable
via the error message.

### What about duplicate skip vs no-op accounting?

`_update_job_counts` is intentionally NOT called on the no-op path.
Recomputing the job totals would be a wasted round-trip and would
also fire any downstream webhooks tied to job completion a second
time. The new test asserts `mock_async_db.db.execute.assert_not_called()`
on the already-skipped path so a future refactor doesn't quietly
re-introduce the thrash.

## Tests

- **Renamed**: `test_skip_import_item_already_skipped` →
  `test_skip_import_item_already_skipped_is_idempotent`. Flipped from
  asserting 400 to 200 + no-op behaviour.
- **All other skip tests pass unchanged** (12 of them):
  `test_skip_import_item_success`, `..._not_found`, `..._job_not_found`,
  `..._no_membership`, `..._viewer_role`, `..._editor_role`,
  `..._completed_status`, `..._pending_status`, `..._job_completes`,
  `..._job_awaiting_review`, `..._job_no_awaiting_review`,
  `..._update_counts_with_failed`.

Total: 13 tests in `TestSkipImportItem`, all passing.

## Local CI status

- `nx run api:lint` — green
- `nx run api:test` — 2541 passed, 100.00% coverage
- (No model / migration changes, so `migrator:check-models` is N/A —
  same state as story 1's run.)
