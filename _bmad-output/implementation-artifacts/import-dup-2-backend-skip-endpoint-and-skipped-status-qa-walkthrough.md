# import-dup-2 — QA Walkthrough

**Story:** `import-dup-2-backend-skip-endpoint-and-skipped-status`
**Date:** 2026-04-25

## Summary

Validation story for the `POST /v1/import-items/{id}/skip` endpoint
that powers the upcoming Approve-Import banner's Skip button. Endpoint
already existed; the one behavior change is **idempotency** — skipping
an already-skipped item now returns 200 (no-op) instead of 400, so
double-taps and slow-network retries don't surface confusing error
toasts.

## Files

| File | Status | Purpose |
|---|---|---|
| `services/api/src/api/v1/import_job/skip_import_item.py` | modified | Split prior `("completed","skipped")` guard: skipped → 200 no-op; completed → 400 (unchanged) |
| `services/api/tests/test_import.py` | modified | Renamed `test_skip_import_item_already_skipped` → `_is_idempotent` and flipped assertion to 200; added `assert_not_called` on `_update_job_counts` |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | `import-dup-2-...: backlog → done` |
| `_bmad-output/implementation-artifacts/import-dup-2-backend-skip-endpoint-and-skipped-status.md` | new | Story spec |
| `_bmad-output/implementation-artifacts/import-dup-2-backend-skip-endpoint-and-skipped-status-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 `skipped` enum value | Existing `String(20)` column already accepts `skipped`; documented in model | `import_item.py` |
| AC #2 Endpoint exists + sets status | Pre-existing implementation | `skip_import_item.py` |
| AC #3 403 for non-owner / non-editor | `test_skip_import_item_no_membership` + `..._viewer_role` | `test_import.py` |
| AC #4 Idempotent (200 on already-skipped) | `test_skip_import_item_already_skipped_is_idempotent` | `test_import.py` |
| AC #5 mutationBus event | Frontend-only abstraction; will land with story 3 | `app/lib/services/import_item_service.dart` |
| AC #6 100% coverage | nx report | `coverage.xml` |

## Manual QA checklist (~5 min)

Run against local stack (`docker compose up`).

### Case A — First skip on a pending item

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/import-items/<item-id>/skip
```

**Expect:** `200`, body `{"id": "...", "status": "skipped",
"updated_at": "..."}`. Job's `succeeded_items` / `failed_items` /
`pending_review_items` recomputed from current item statuses.

### Case B — Second skip on the same item (idempotency)

Re-run the same `curl` immediately.

**Expect:** `200`, body has `"status": "skipped"`. No change to
`updated_at`. Job counts are NOT recomputed (no extra DB round-trip).

### Case C — Skip a completed item (regression)

Pick an item with `status == "completed"` (i.e. one whose
`created_recipe_id` is set).

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/import-items/<completed-item-id>/skip
```

**Expect:** `400`, body `{"error_message": "Cannot skip item in
completed status", "error_code": "IMPORT_ITEM_INVALID_STATUS"}`.

### Case D — Skip without permission

Authenticated as a user whose membership on the import job's recipe
book is `viewer` (or no membership at all).

**Expect:** `403`, body mentions "permission".

## Test inventory

13 tests total in `TestSkipImportItem`. Renamed 1, all 13 passing.

| # | Test | What it proves |
|---|---|---|
| 1 | `test_skip_import_item_success` | Happy-path success (status flips, response body shape) |
| 2 | `test_skip_import_item_not_found` | 404 on unknown item id |
| 3 | `test_skip_import_item_job_not_found` | 404 if parent import_job missing |
| 4 | `test_skip_import_item_no_membership` | 403 with no membership |
| 5 | `test_skip_import_item_viewer_role` | 403 with viewer role |
| 6 | `test_skip_import_item_editor_role` | 200 with editor role |
| 7 | `test_skip_import_item_completed_status` | 400 on `status == "completed"` |
| 8 | `test_skip_import_item_already_skipped_is_idempotent` | **200 no-op on already-skipped** (new behavior) |
| 9 | `test_skip_import_item_pending_status` | Pending → skipped works |
| 10 | `test_skip_import_item_job_completes` | Job rolls to `completed` when last item handled |
| 11 | `test_skip_import_item_job_awaiting_review` | Job rolls to `awaiting_review` when others pending |
| 12 | `test_skip_import_item_job_no_awaiting_review` | Job stays in current state otherwise |
| 13 | `test_skip_import_item_update_counts_with_failed` | Failed items are accounted for in `_update_job_counts` |

## Local CI

| Gate | Result |
|---|---|
| `nx run api:lint` | green |
| `nx run api:test` | 2541 pass, 100.00% coverage |
