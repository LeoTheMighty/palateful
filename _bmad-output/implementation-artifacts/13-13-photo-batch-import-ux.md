# Story 13.13: Photo Batch Import UX

**Status:** complete

## Summary

Redesign the photo capture screen to use the new `ParserBatch` API from story 13.12. The new flow minimizes clicks for the common case (one recipe, N photos), supports the uncommon case (multiple recipes in one selection) via a tap-to-assign grouping view with no drag-and-drop, uploads images in the background as soon as they're picked, and — critically — **drops the user back to the import hub immediately on submit** so they can start another import without waiting. Polling and status surfaces are owned by story 13.14; this story is the picker + grouping + submit flow only.

## User Value

Leo's testimony: *"Right now I pick 3 photos of one recipe's pages and it creates 3 broken recipes. I want to say 'obviously these are the same recipe' with one tap, submit, and immediately pick more photos without waiting for OCR to finish."* This story delivers exactly that: one-tap happy path, progressive disclosure for grouping, and non-blocking submit.

## Acceptance Criteria

### Picking Images

1. Tapping the image source affordance opens the existing "Take Photo" / "Choose from Gallery" bottom sheet (keep `_showImageSourceDialog` behavior from `photo_capture_screen.dart`)
2. Selecting N images from gallery adds them all to the local selection (existing behavior)
3. **New:** As soon as each image is added to selection, the app **begins uploading it to S3 in the background** via the existing `getParserUploadUrl` → S3 PUT flow — the user does not need to tap a "process" button first
4. Upload progress per image is visible on the thumbnail (small circular progress overlay, becomes a check on success, red X on failure)
5. If an upload fails, the user can tap the failed thumbnail to retry just that one image; other uploads are unaffected
6. The user can remove a thumbnail (existing close button). Removing it cancels the upload if still in flight.
7. Add-more and remove behaviors work during and after upload

### Single-Screen Decision

8. When at least one image has been picked and all uploads have completed (or are in a clearly ready state), the screen shows two affordances below the thumbnail strip:
   - **Primary button** (large, filled, full-width): **"Import as one recipe"** — this is the default, hero action
   - **Secondary affordance** (tertiary text link, smaller, below primary): **"These are separate recipes →"**
9. If only one image is selected, the secondary link is hidden (there's nothing to group)
10. Both affordances are disabled until **every** image has a completed S3 upload
11. Destination book selector (`_buildBookSelector` from existing screen) is preserved above the buttons

### "Import as one recipe" — Happy Path

12. Tapping "Import as one recipe" calls the new `POST /v1/parser/batches` endpoint with `group_index=0` for every image
13. On success, the screen **immediately pops back to the import hub** (`AddRecipeSheet` or wherever the user came from) — there is **no wait screen**, no recipe preview, no status spinner on this screen
14. A lightweight snackbar confirms: "Started import — we'll let you know when it's ready"
15. On submission failure (network error, auth, etc.), show an error inline and keep the screen so the user can retry

### "These are separate recipes →" — Grouping View

16. Tapping the secondary link transitions to a grouping view **within the same screen** (not a new route — just a state change in `_PhotoCaptureScreenState`)
17. Grouping view shows all images in a **grid** (not horizontal strip), each image badged `Recipe 1`, `Recipe 2`, ... defaulting to **one recipe per image** (so N images → N recipes by default)
18. Above the grid, a live counter: **"Will create N recipes"** that updates as assignments change
19. Below the grid, a horizontal chip row: `Recipe 1`, `Recipe 2`, ..., `+ New recipe`. The currently-selected chip is visually highlighted.
20. Interaction model: **tap an image to select it, then tap a recipe chip to assign it to that group.** Multi-select (long-press or a "Select" toggle) allows batching multiple images into one group in one action. No drag-and-drop.
21. An image's badge updates immediately on assignment. Recipe numbers stay contiguous (if Recipe 2 ends up empty after reassignment, the UI re-numbers remaining recipes so there are no gaps).
22. A "Back" affordance returns the user to the single-screen decision view without losing assignments
23. A primary button at the bottom — **"Create N recipes"** — becomes enabled as soon as every image has a valid group assignment (which is always, since the default is one-per-image)
24. Tapping "Create N recipes" calls `POST /v1/parser/batches` with the assembled `items: [{ s3_key, group_index }]`. Same post-submission behavior as AC #13–14: immediate pop-back + snackbar.

### Removed Behavior

25. The existing `_buildRecipePreview` recipe preview / approval flow inside `photo_capture_screen.dart` is **removed**. Review now happens exclusively via the existing `ImportReviewListScreen` → `ImportItemReviewScreen` path, reached from the Activity / Needs Review surface.
26. `_startImportPipeline`, `_startImportPolling`, `_pollImportJob`, `_loadImportItems`, `_approveImport`, `_dismissImport`, `_importJobId`, `_importItem`, `_parsedRecipe`, `_isApproving`, and `_importPollTimer` are deleted from `_PhotoCaptureScreenState` — the screen no longer owns any review or import-job polling state
27. `_startOcrPolling`, `_pollTimer`, `_ocrPollCount`, and all `_JobResult` plumbing for tracking parser-job status after submit are also deleted — this screen no longer polls parser jobs. Status watching is owned by story 13.14's `ImportBatchesController`.

### Not Blocking New Imports

28. After submit + pop-back, the user can immediately open the photo capture screen again and start another batch. There is no global lock, no "please wait for previous import to finish" gate. Each batch is independent.

## Technical Approach

### API Client

Add to `app/lib/core/services/api_client.dart`:

```dart
Future<Response> createParserBatch({
  required String recipeBookId,
  required List<Map<String, dynamic>> items, // [{s3_key, group_index}]
}) {
  return _dio.post('/v1/parser/batches', data: {
    'recipe_book_id': recipeBookId,
    'items': items,
  });
}

Future<Response> getParserBatch(String batchId) {
  return _dio.get('/v1/parser/batches/$batchId');
}

Future<Response> listParserBatches({bool activeOnly = true, int limit = 20}) {
  return _dio.get('/v1/parser/batches', queryParameters: {
    if (activeOnly) 'active': true,
    'limit': limit,
  });
}
```

### Screen State Refactor

Rewrite `app/lib/features/recipes/add_recipe/photo_capture_screen.dart` around a small state enum:

```dart
enum _Phase { picking, grouping, submitting }
```

Per-image upload state tracked on the existing `_SelectedImage` model (add `String? s3Key`, `UploadStatus uploadStatus`, `double? uploadProgress`).

Background upload logic: when `_selectedImages` gains an entry, kick off an async upload for it. The screen only becomes "submit-ready" when every image has `uploadStatus == UploadStatus.complete`.

Grouping state: `Map<int /* image index */, int /* group_index */>`, plus a helper to compact group indices after reassignment.

### Files Affected

**Modified:**
- `app/lib/features/recipes/add_recipe/photo_capture_screen.dart` — major rewrite per AC above
- `app/lib/core/services/api_client.dart` — new `createParserBatch`, `getParserBatch`, `listParserBatches` methods

**No route changes.** Existing routes to `PhotoCaptureScreen` continue to work.

## Out of Scope

- The in-progress strip / live status UI on the import hub (story 13.14)
- `ImportBatchesController` / Riverpod provider for live state (story 13.14)
- Reviewing extracted recipes (existing `ImportItemReviewScreen` unchanged)
- Migrating any other import path to batches
- Handling S3 upload backpressure for 20+ images — the picker's existing limits are fine

## Dependencies

- **Blocks on 13.12** — requires the `POST /v1/parser/batches` endpoint and the backend fanout logic to exist
- Does not block on 13.14 — this story can ship and users will still see their imports surface via the existing Needs Review / Activity UI, just without the new in-progress strip
