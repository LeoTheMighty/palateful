# QA Walkthrough: MVP.9 — Clear All Failed + Swipe to Dismiss

## What shipped

1. **"Clear all failed (N)" AppBar action** on `ImportHistoryScreen` — shown only when at least one failed item exists. N = count of currently-visible failed items across all failed jobs.
2. **Confirmation dialog** — tapping the button opens an `AlertDialog` with singular/plural-aware copy:
   - `"Dismiss 1 failed import? This can't be undone."`
   - `"Dismiss 5 failed imports? This can't be undone."`
   - `[Cancel]` / `[Dismiss all]` buttons.
3. **Bulk dismiss wired to backend** — on confirm, calls `dismissAllFailedImports()` (mvp-7 endpoint) and drops all failed groups from local state optimistically. Shows a snackbar with the server-returned `dismissed_count`. On failure, restores the local snapshot and shows an error snackbar. No undo (the confirm dialog is the safety net).
4. **Swipe-left-to-dismiss** on each failed item row — wrapped in a `Dismissible` with `DismissDirection.endToStart` and a red delete-icon background. Calls the same `_dismissSingleItem` handler from mvp-8, which hits `POST /v1/import-items/{id}/dismiss`. Swipe is scoped to failed rows only.
5. **Swipe-to-dismiss keys** are `ValueKey('failed-item-$itemId')` so Flutter tracks rows correctly across rebuilds.
6. **Widget tests**: 4 new test cases in `import_history_screen_test.dart`:
   - Header button hidden when zero failed items
   - Header button shows `"Clear all failed (2)"` for two failed items
   - Tapping Clear all → Cancel → no API call, rows still visible
   - Tapping Clear all → Dismiss all → API called, rows gone, snackbar shown

## QA checklist

### Automated
- [x] `flutter test test/features/activity/import_history_screen_test.dart` — **4/4 pass**
- [x] `flutter analyze lib/features/activity/import_history_screen.dart` — clean (only 2 pre-existing warnings unrelated to this story)

### Manual (to run post-deploy)
- [ ] Seed 3 failed URL imports. Open Import Activity. Verify header shows `"Clear all failed (3)"`.
- [ ] Tap the header button → dialog appears with `"Dismiss 3 failed imports? This can't be undone."` → tap Cancel → rows stay, no network call made.
- [ ] Tap header again → confirm → all 3 rows vanish → snackbar says `"Dismissed 3 imports"` → refresh → stays cleared.
- [ ] Error path: with the server unreachable, tap Clear all → confirm → optimistic rows disappear → snackbar says `"Failed to clear: ..."` → rows restored.
- [ ] Swipe a failed item left → row animates off-screen, `dismissImportItem` fires, item is gone after refresh.
- [ ] Confirm swipe-to-dismiss is NOT available on review items (only failed items get wrapped in `Dismissible`).

### Known tradeoffs / follow-ups
- **No bulk undo snackbar**. The confirmation dialog is the only safety net for the bulk action. Single swipe-dismiss still gets the implicit optimistic-revert-on-error from `_dismissSingleItem` but there's no explicit "Undo" button for an individual swipe dismiss on this screen (mvp-8 added that for the Add Recipe strip, not here).
- **Dismissible only on failed rows** — deliberately scoped. Expanding swipe to review/completed rows would touch state transitions the backend doesn't support.
- **Count in header reflects currently-visible items**, not total in DB. Bulk endpoint dismisses everything on the server anyway, and the snackbar shows the server's count, so this is cosmetic only.

## Files touched

- `app/lib/features/activity/import_history_screen.dart` (modified — header action, `_handleClearAllFailed`, `_totalFailedItemCount`, `Dismissible` wrapper)
- `app/test/features/activity/import_history_screen_test.dart` (new — 4 widget tests)
- `_bmad-output/implementation-artifacts/mvp-9-qa-walkthrough.md` (new)
