# Story MVP.8: Flutter Failed-State Row UI with Retry + Dismiss

Status: ready-for-dev

## Story

As a user looking at the Add Recipe screen or the import history hub,
I want every failed import to show inline **Retry** and **Dismiss** buttons,
so that I can recover from failures in one tap instead of staring at ghost imports I can't do anything about.

## Context

Today, failed imports are either invisible (the "In Progress" strip keeps showing them as processing until someone dives into the database) or visible-but-untouchable (they sit in the import history screen with no actions). Leo's subjective description: *"I import a URL instead, and now there are TWO ghost recipes sitting there mocking me."*

With mvp-5 + mvp-6 + mvp-7 landed, the backend now supports:
- Stuck imports are correctly marked `failed` by the sweeper
- `POST /v1/imports/items/{id}/retry` dispatches the resumed task
- `POST /v1/imports/items/{id}/dismiss` hides the row permanently

This story wires both buttons into the Flutter UI on the two surfaces that currently show failed imports: the **import batches strip** on the Add Recipe screen (`app/lib/features/recipes/add_recipe/import_batches_strip.dart`) and the **import history screen** (`app/lib/features/activity/import_history_screen.dart` — confirm exact path at implementation time).

This story does **not** add swipe-to-dismiss or a "Clear all failed" button — those are mvp-9.

## Acceptance Criteria

1. On the Add Recipe screen's import batches strip, any batch whose `status == "failed"` (or whose linked `ImportJob.status == "failed"`) renders with:
   - A red `error_outline` icon
   - Title text (recipe name if known, else "Photo import")
   - Subtitle: short failure reason (`error_message` truncated to ~60 chars, or "Import failed")
   - Two inline buttons: `[Retry]` and `[Dismiss]`
2. Tapping **Retry**:
   - Optimistically updates the row to show a spinner and "Retrying…" text
   - Calls `POST /v1/imports/items/{item_id}/retry` (for each failed item under the job — if there's only one, it's one call; if multiple, fire them in parallel)
   - On success: the row flips back to "processing" state and the existing polling picks it up
   - On failure (network error, backend 4xx): reverts to failed state and shows a snackbar with the error
3. Tapping **Dismiss**:
   - Optimistically removes the row from the list immediately
   - Calls `POST /v1/imports/items/{item_id}/dismiss` (or the bulk endpoint if dismissing the whole job — see Dev Notes)
   - Shows a snackbar `Import dismissed [Undo]` with a 4-second timeout
   - If the user taps **Undo** within 4 seconds: restore the row in the local state. **No backend un-dismiss** — the snackbar undo is local-only, which means if the user waits out the snackbar, the backend dismissal is permanent and the row will not come back on refresh
   - **Important UX nuance**: because backend dismissal fires immediately (not on snackbar expiry), the "undo" restores local state only. If the user refreshes before undoing, the row is gone. This is the tradeoff for skipping backend un-dismiss. Document this in the Dev Notes of the implementation — acceptable for MVP, flag in retrospective if it causes user pain.
4. Same buttons and behavior apply on the **import history screen** (`import_history_screen.dart` or wherever failed imports are listed today), so users have two places to recover from a failure.
5. The retry and dismiss actions work for imports that are stuck-failed by the sweeper (parent `ImportJob.status == "failed"` but child item statuses may still be mid-pipeline like `"extracting"` or `"matching"`). Verify via manual test after mvp-5 ships.
6. After a successful retry, the row's polling resumes via the existing `import_batches_provider` refresh cycle — this story does NOT build a new poller.
7. Widget tests:
   - Failed row renders with both buttons visible
   - Tap Retry → API called, row optimistically updates to processing
   - Tap Retry → API error → row reverts and snackbar shows
   - Tap Dismiss → row immediately gone from list, snackbar visible
   - Tap Undo within 4s → row restored in local state
   - Wait 4s → row stays gone, snackbar auto-dismisses
8. Integration smoke: retry a failed URL import end-to-end via the dev build, confirm the row transitions failed → processing → succeeded.

## Tasks / Subtasks

- [ ] Task 1: API client methods (AC: #2, #3)
  - [ ] Modify `app/lib/core/services/api_client.dart`
  - [ ] Add `retryImportItem(String itemId)` → `POST /v1/imports/items/{id}/retry`
  - [ ] Add `dismissImportItem(String itemId)` → `POST /v1/imports/items/{id}/dismiss`
  - [ ] Return typed responses matching the backend's response shape

- [ ] Task 2: Failed-state row widget (AC: #1)
  - [ ] Locate the widget that renders one batch row in `app/lib/features/recipes/add_recipe/import_batches_strip.dart` — likely a private `_BatchRow` or `_StatusRow` widget
  - [ ] Add a conditional branch: when `batch.status == "failed"` OR any linked `ImportJob.status == "failed"`, render the failed variant
  - [ ] Failed variant: red error icon, title, truncated error subtitle, `[Retry]` + `[Dismiss]` buttons in a trailing `Row`
  - [ ] Use existing theme tokens for colors (`colorScheme.error`, `appColors.errorLight`) — do not hardcode

- [ ] Task 3: Retry action wiring (AC: #2)
  - [ ] Add a `_handleRetry` method that:
    - Sets a local `_retrying: Set<String>` state to show the spinner
    - Calls `apiClient.retryImportItem(itemId)` (or parallel calls for multi-item jobs via `Future.wait`)
    - On success: calls `ref.read(importBatchesProvider.notifier).refresh()` to pick up the new state from the backend
    - On failure: removes from `_retrying`, shows snackbar via `ScaffoldMessenger`
  - [ ] If the job has multiple failed items, retry each in parallel. If any fail, treat the whole retry as failed and show the count in the error message

- [ ] Task 4: Dismiss action wiring (AC: #3)
  - [ ] Add a `_handleDismiss` method that:
    - Optimistically removes the row from local state (via `importBatchesProvider` notifier method `locallyRemoveBatch(batchId)` — add this method if it doesn't exist)
    - Calls `apiClient.dismissImportItem(itemId)` immediately — fire and forget, but await internally so we can catch errors
    - Shows a `SnackBar` with text "Import dismissed" and an `Undo` action button, duration 4 seconds
    - If Undo tapped before the snackbar expires: call `importBatchesProvider.notifier.locallyRestoreBatch(batchId)` to put it back in local state. **Do NOT call a backend un-dismiss endpoint** — there isn't one
    - If the dismiss API call fails: revert the optimistic removal, show an error snackbar
  - [ ] If the job has multiple failed items, dismissing the job row dismisses all of them — use the bulk endpoint or fire parallel single-dismiss calls

- [ ] Task 5: Apply the same widget to import history screen (AC: #4)
  - [ ] Locate the import history screen (grep `import_history` or `ImportHistoryScreen` under `app/lib/`)
  - [ ] If the failed row layout can be extracted into a shared widget (`app/lib/features/activity/widgets/failed_import_row.dart`), do that and reuse it on both surfaces
  - [ ] If the two surfaces diverge too much to share, duplicate the retry/dismiss handler logic into a shared method in a utility file

- [ ] Task 6: Provider updates (AC: #6)
  - [ ] Modify `app/lib/features/recipes/add_recipe/state/import_batches_provider.dart`
  - [ ] Add `locallyRemoveBatch(String batchId)` and `locallyRestoreBatch(String batchId, BatchData data)` methods for the optimistic update / undo flow
  - [ ] Make sure the next `refresh()` call rehydrates correctly from the backend (which should no longer return the dismissed batch)

- [ ] Task 7: Widget tests (AC: #7)
  - [ ] Test file: `app/test/features/recipes/add_recipe/import_batches_strip_test.dart`
  - [ ] Pump the strip with a failed batch fixture, assert both buttons render
  - [ ] Tap Retry: mock `apiClient.retryImportItem` to succeed, verify optimistic state and refresh call
  - [ ] Tap Retry: mock failure, verify revert and snackbar
  - [ ] Tap Dismiss: mock `apiClient.dismissImportItem` to succeed, verify row is gone from list
  - [ ] Tap Undo: verify row comes back
  - [ ] Wait 4s: verify snackbar auto-closes and row stays gone

- [ ] Task 8: Manual smoke test (AC: #8)
  - [ ] Force a URL import to fail (use an invalid URL), observe the failed row, tap Retry, confirm it recovers or re-fails cleanly
  - [ ] Force a photo import to fail, same flow
  - [ ] Dismiss a failed import, refresh the screen, confirm it does not come back

## Dev Notes

- **Undo is local-only.** The snackbar undo restores Flutter state only. If the user refreshes before undoing, the dismissed row is gone forever. This is acceptable for MVP — document it visibly in the Dev Notes of any code that implements the snackbar.
- **Optimistic updates** are the way: on Dismiss, remove from UI before the API call completes. On Retry, flip to "retrying" before the API call completes. This makes the UI feel fast and responsive. On API failure, revert.
- **Multi-item jobs**: an `ImportJob` can have multiple `ImportItem`s. For MVP, treat a failed job as a single row in the strip (the existing behavior). Retry/dismiss the job means retry/dismiss all failed items under it — fire parallel API calls or use the bulk endpoint if it makes sense.
- **Don't build new polling infrastructure**. Rely on `importBatchesProvider.refresh()` — it already polls.
- **Error message truncation**: use `String.substring(0, min(60, s.length))` with an ellipsis. Don't try to parse structured error codes for fancy messaging — that's a future polish.
- **Icon choice**: `Icons.error_outline` for the failed state icon. Match the outlined-icon style already used on this screen for consistency.

### Project Structure Notes

- Shared failed-row widget should go under `app/lib/features/activity/widgets/` if reused across surfaces, or stay private in `import_batches_strip.dart` if not
- Widget test convention: `app/test/features/...`

### References

- Add Recipe surface: `app/lib/features/recipes/add_recipe/import_batches_strip.dart`
- Provider: `app/lib/features/recipes/add_recipe/state/import_batches_provider.dart`
- API client: `app/lib/core/services/api_client.dart`
- Import history screen: location TBD — grep `ImportHistoryScreen` at implementation
- [Story: mvp-6-retry-endpoint.md]
- [Story: mvp-7-dismiss-endpoints.md]
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
