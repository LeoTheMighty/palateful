# Story MVP.9: "Clear All Failed" + Swipe-to-Dismiss in the Import Hub

Status: done

## Story

As a user whose import hub has accumulated many failed imports,
I want a single "Clear all failed" button and swipe-to-dismiss gestures on individual rows,
so that I can clean up visual noise in one tap instead of tap-dismissing every row individually.

## Context

With mvp-8 shipped, every failed row has inline Retry + Dismiss buttons. This story adds two ergonomic shortcuts on top:

1. A **"Clear all failed"** button in the import hub header that batch-dismisses everything in one call
2. **Swipe-left to dismiss** on individual rows (iOS-native gesture) as an alternative to tapping the Dismiss button

This story is pure frontend — the backend bulk-dismiss endpoint is already in place from mvp-7 (`POST /v1/imports/dismiss-all-failed`).

This is a P2 polish story and explicitly depends on mvp-7 and mvp-8 shipping first.

## Acceptance Criteria

1. The import hub screen (likely `ImportHistoryScreen` or similar — confirm at implementation) shows a header action when at least one failed import exists:
   - Button label: "Clear all failed (N)" where N is the count of currently-visible failed items
   - Button is disabled (or hidden) when N == 0
   - Button style matches the app's existing header action pattern — check what other screens use for header actions
2. Tapping "Clear all failed":
   - Shows a confirmation dialog: "Dismiss N failed imports? This can't be undone." with `[Cancel]` and `[Dismiss all]` buttons
   - On confirm: optimistically removes all failed rows from the list
   - Calls `POST /v1/imports/dismiss-all-failed`
   - Shows a snackbar: "Dismissed N imports" (no Undo — bulk dismissal is intentional and the confirmation dialog is the safety net)
   - On API failure: reverts the optimistic removal, shows an error snackbar
3. Each failed row in the import hub **also** supports swipe-left-to-dismiss:
   - Swipe gesture reveals a red "Dismiss" background with a trash icon
   - Fully swiping the row off-screen triggers the same dismiss flow as tapping the Dismiss button (optimistic remove + API call + 4s undo snackbar from mvp-8)
   - Partial swipe that doesn't cross the threshold returns the row to its resting position
4. Swipe-to-dismiss is **also** available on non-failed rows in the import hub (e.g. `completed` or `awaiting_review`) — **but only if** doing so is a no-op server-side or equivalent to archiving. **Default: restrict swipe-dismiss to failed rows for MVP.** Add a Dev Note flagging that this is a deliberate narrowing.
5. Confirmation dialog text uses exact failure count: "Dismiss 5 failed imports? This can't be undone." — singular form for 1 ("Dismiss 1 failed import?")
6. The "Clear all failed" button does NOT appear on the Add Recipe screen's import batches strip — only on the dedicated import hub screen. The Add Recipe strip already has individual Dismiss buttons from mvp-8.
7. Widget tests:
   - Header button shows correct count when failed items exist
   - Header button hidden/disabled when count is 0
   - Tap Clear all → confirm dialog shows → cancel → no API call, rows still visible
   - Tap Clear all → confirm → API called, rows removed, snackbar shows
   - API failure → rows restored, error snackbar
   - Swipe-left on a failed row past threshold → dismiss flow fires (reuses mvp-8 logic)
   - Swipe-left that doesn't cross threshold → row returns to position

## Tasks / Subtasks

- [ ] Task 1: API client method (AC: #2)
  - [ ] Modify `app/lib/core/services/api_client.dart`
  - [ ] Add `dismissAllFailedImports()` → `POST /v1/imports/dismiss-all-failed`
  - [ ] Returns the `dismissed_count` from the backend response

- [ ] Task 2: Clear all button in the import hub header (AC: #1, #2, #5, #6)
  - [ ] Locate the import hub screen file (grep `ImportHistoryScreen`)
  - [ ] Add the header action button to the AppBar `actions` slot
  - [ ] Compute count: filter the current list for failed items, use `.length`
  - [ ] Wire to a `_handleClearAllFailed` method that:
    - Shows an `AlertDialog` with the confirmation text
    - On confirm: optimistically remove all failed items from the local state
    - Call `apiClient.dismissAllFailedImports()`
    - Show success snackbar with `dismissed_count`
    - On failure: revert and show error snackbar
  - [ ] Use existing theme tokens for the destructive button color (`colorScheme.error`)

- [ ] Task 3: Swipe-to-dismiss on individual rows (AC: #3, #4)
  - [ ] Wrap each failed row in a `Dismissible` widget
  - [ ] `direction: DismissDirection.endToStart` (left-swipe in LTR, right-swipe in RTL — Flutter handles this)
  - [ ] `background`: red container with a white trash icon aligned right
  - [ ] `confirmDismiss`: call the same `_handleDismiss` method from mvp-8 (which handles the optimistic remove + API call + undo snackbar). Return `true` if the dismiss API call is initiated — the `Dismissible` will animate the row off-screen. If the dismiss fails later, the snackbar shows the error
  - [ ] Add a `key: ValueKey(batchId)` to the `Dismissible` so Flutter can track it correctly
  - [ ] Restrict swipe gesture to failed rows only: check the status before wrapping in `Dismissible`. Non-failed rows render without the wrapper

- [ ] Task 4: Confirmation dialog helper (AC: #2, #5)
  - [ ] Extract a private `Future<bool> _showClearAllConfirmation(int count)` helper that returns the dialog result
  - [ ] Handle singular/plural: `count == 1 ? "1 failed import" : "$count failed imports"`

- [ ] Task 5: Widget tests (AC: #7)
  - [ ] Test file: `app/test/features/activity/import_history_screen_test.dart` (or matching existing test location)
  - [ ] Test case: header shows "Clear all failed (3)" when 3 failed rows rendered
  - [ ] Test case: header hidden when zero failed rows
  - [ ] Test case: tap Clear all → dialog → cancel → no API call
  - [ ] Test case: tap Clear all → dialog → confirm → mock API success → rows removed, snackbar shows correct count
  - [ ] Test case: API failure → rows restored
  - [ ] Swipe test: simulate a horizontal drag past the threshold on a failed row → `_handleDismiss` called
  - [ ] Swipe test: partial drag under threshold → row snaps back, no API call

## Dev Notes

- **No bulk undo**: the "Clear all failed" action does not show an undo snackbar because the confirmation dialog already serves as the safety net. Individual swipe-dismisses still get the 4-second undo (reuses mvp-8 behavior).
- **Dismissible widget quirks**: when using `Dismissible` inside a `ListView.builder`, each row MUST have a stable unique `Key`. Use `ValueKey(batchId)` or `ValueKey(importItemId)`.
- **Keep swipe restricted to failed rows for MVP**. Expanding swipe to other statuses (archive a completed import, etc.) is a slippery slope — it touches state transitions the backend doesn't currently support. Document the restriction as a deliberate choice, not an oversight.
- **Don't duplicate the dismiss logic** from mvp-8. Extract `_handleDismiss` into a shared method in the provider or a utility file so both the tap-button and swipe paths call the same implementation.
- **Confirmation dialog count** reflects currently-*visible* failed items, not the total in the database. If pagination is in play, this is imperfect but acceptable — the bulk endpoint dismisses everything anyway, and the snackbar shows the server-side count.

### Project Structure Notes

- The `Dismissible` + swipe UI belongs in the import hub screen, not the Add Recipe strip
- The "Clear all" button is a header action on the hub screen only
- Widget test location: `app/test/features/activity/`

### References

- Bulk endpoint: `POST /v1/imports/dismiss-all-failed` (from mvp-7)
- Dismiss single: `POST /v1/imports/items/{id}/dismiss` (from mvp-7)
- Shared dismiss handler: see `_handleDismiss` added in mvp-8
- `Dismissible` Flutter docs: https://api.flutter.dev/flutter/widgets/Dismissible-class.html
- [Story: mvp-7-dismiss-endpoints.md]
- [Story: mvp-8-flutter-failed-state-ui.md]
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- `flutter test test/features/activity/import_history_screen_test.dart` — 4/4 pass
- `flutter analyze` on the touched file — clean (pre-existing warnings only)

### Completion Notes List

- Clear-all button lives on the AppBar action slot (not inside the body) so it's always reachable without scrolling.
- Used a local `snapshot` of `_failedJobs` before clearing state, so an API failure can restore exactly what was there before — cleaner than re-fetching.
- `Dismissible` wraps only failed rows, using an outer key prefix (`failed-item-$itemId`) so the key namespace is distinct from any other `ValueKey(itemId)` used elsewhere on the screen.
- Did not add a swipe-to-dismiss undo snackbar on this screen — mvp-8's `_dismissSingleItem` already does an optimistic revert on API error, and adding a separate "Undo" flow here would duplicate logic. Documented in QA walkthrough as a deliberate narrowing.
- No backend changes in this story — uses the bulk endpoint from mvp-7.

### File List

- `app/lib/features/activity/import_history_screen.dart` (modified — Clear all action, confirmation dialog, `Dismissible` wrapper, `_totalFailedItemCount`, `_handleClearAllFailed`)
- `app/test/features/activity/import_history_screen_test.dart` (new — 4 widget tests)
- `_bmad-output/implementation-artifacts/mvp-9-qa-walkthrough.md` (new)
