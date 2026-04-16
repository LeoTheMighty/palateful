# QA Walkthrough: MVP.8 — Flutter Failed-State UI

## What shipped

1. **API client methods** in `api_client.dart`:
   - `retryImportItem(itemId)` → `POST /v1/import-items/{id}/retry`
   - `dismissImportItem(itemId)` → `POST /v1/import-items/{id}/dismiss`
   - `dismissAllFailedImports()` → `POST /v1/import-jobs/dismiss-all-failed`
2. **`import_batches_strip.dart`** — failed batch rows now show an inline `[Retry]` + `[Dismiss]` button row underneath the batch header.
   - Retry: fetches all failed items under each linked `ImportJob` via `listImportItems(jobId, status: 'failed')`, then fires `retryImportItem` for every id in parallel. On success, triggers `importBatchesProvider.refresh()` so the row flips back to "processing". On failure, reverts the spinner and shows an error snackbar.
   - Dismiss: optimistically hides the row via `importBatchesProvider.notifier.locallyRemoveBatch(batchId)`, fires the backend dismiss calls fire-and-forget, shows a 4-second snackbar with `Undo`. Undo restores local state only — if the backend call already committed, the next refresh will agree.
3. **`import_batches_provider.dart`** — new `locallyRemoveBatch` and `locallyRestoreBatch` methods on the notifier to support the optimistic update flow.
4. **`import_history_screen.dart`** — the existing "Failed" section now:
   - Shows a **Retry** icon button next to the existing Dismiss (X) button on every failed item
   - Switches the dismiss path from `skipImportItem` (which set `status=skipped`, wrong semantics) to the new `dismissImportItem` (which sets `dismissed_at`, the correct hide action)
5. **Widget tests**: 3 new tests in `import_batches_strip_test.dart` covering failed-row rendering, Retry dispatch, and Dismiss + snackbar.

## UX details worth knowing

- **Undo is local-only.** The snackbar undo does NOT call a backend un-dismiss endpoint (one doesn't exist). If the user refreshes before tapping Undo, the dismissed row is gone forever. This is documented in `_handleDismiss` source comments and in the epic's explicit cuts list.
- **Retry button stays disabled** during the retry call to prevent double-taps.
- **Retry calls per-item in parallel** via `Future.wait`. For a 1-image failed batch that's 1 list call + 1 retry call (2 total). For a 3-image batch it's 1 list + 3 retries.
- **Dismiss fires backend calls fire-and-forget** — the local state flips to hidden immediately, the backend catch-up happens in the background. On backend failure, the optimistic hide is rolled back via `locallyRestoreBatch`.

## QA checklist

### Automated
- [x] `flutter test test/features/recipes/add_recipe/import_batches_strip_test.dart` — 3/3 pass
- [x] `flutter test test/features/home/home_screen_test.dart test/features/recipes/add_recipe/import_batches_strip_test.dart test/share_import_test.dart` — **16/16 pass** (no regressions on adjacent tests)
- [x] `flutter analyze lib/features/recipes/add_recipe/widgets/import_batches_strip.dart lib/features/recipes/add_recipe/state/import_batches_provider.dart lib/core/services/api_client.dart lib/features/activity/import_history_screen.dart` — clean (only 2 pre-existing warnings in `import_history_screen.dart` unrelated to this story)

### Manual (to run post-deploy)
- [ ] Force a URL import to fail (invalid URL). Open the app → the batch strip on the Add Recipe sheet shows a "Failed" row with inline Retry + Dismiss buttons.
- [ ] Tap Retry → row should briefly show "Retrying…" → server accepts → the row flips back to "processing" (via refresh). If the retry fails, an error snackbar appears.
- [ ] Tap Dismiss → row disappears immediately. Snackbar shows "Import dismissed [Undo]" for 4 seconds. Tap Undo within the window → row comes back. Wait out the snackbar → row stays gone after refresh.
- [ ] Open the Import Activity hub. A failed item shows a **refresh** icon next to the **X** icon in the row trailing. Tapping refresh retries; tapping X dismisses.
- [ ] Sweeper case: kill a worker mid-extract, let mvp-5's sweeper mark the job failed. The strip should still be able to retry — since the parent `ImportJob.status == "failed"`, the retry endpoint accepts the request even though the item itself is mid-pipeline, and the stage marker resumes from the right place.

### Known tradeoffs / follow-ups
- **No backend un-dismiss** — snackbar undo is local-only. If it causes user confusion, open a follow-up to add `POST /v1/import-items/{id}/undismiss`.
- **Retry fires N parallel per-item calls** rather than a single batch call. For typical 1-2 item batches this is fine; for a hypothetical 10+ image batch it's 10 concurrent POSTs. Could batch server-side with a job-level retry endpoint if this becomes painful.
- **Mvp-8 does NOT add swipe-to-dismiss or "Clear all failed" in the hub** — those are mvp-9.
- **Pre-existing warnings** in `import_history_screen.dart` (`error_banner.dart` unused import, unused `_errorDetail` field) are left alone; not introduced by this story.

## Files touched

- `app/lib/core/services/api_client.dart` (modified — 3 new methods)
- `app/lib/features/recipes/add_recipe/state/import_batches_provider.dart` (modified — locallyRemoveBatch / locallyRestoreBatch)
- `app/lib/features/recipes/add_recipe/widgets/import_batches_strip.dart` (modified — failed actions row, Retry/Dismiss handlers)
- `app/lib/features/activity/import_history_screen.dart` (modified — Retry button on failed items, dismiss path switched to `dismissImportItem`)
- `app/test/features/recipes/add_recipe/import_batches_strip_test.dart` (new — 3 widget tests)
- `_bmad-output/implementation-artifacts/mvp-8-qa-walkthrough.md` (new)
