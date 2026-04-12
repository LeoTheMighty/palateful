# Story 13.14: Live Import Progress Controller & Strip

**Status:** complete

## Summary

Introduce an app-level `importBatchesProvider` (Riverpod) that polls the new `GET /v1/parser/batches?active=true` endpoint on a consistent interval, holds the list of active and recently-completed batches in memory, and **survives navigation** (so status polling doesn't die when the user leaves the photo capture screen). Surface this state as a compact **"In progress" strip** on the Add Recipe sheet (the import hub) showing each active batch as a row with a progress pill, an expandable disclosure for per-image OCR text debug, and a "Just started" highlight on freshly-submitted batches. This is the story that makes the non-blocking flow from 13.13 actually feel non-blocking.

## User Value

Three things this unlocks, all of which Leo asked for directly:
1. **Visibility without navigation** — "the thing I just started" is visible right where I started it, with live progress
2. **Debug affordance** — tap to see extracted OCR text per image so I can tell when OCR is the weak link vs. when extraction is
3. **Durable state** — if I close the photo picker and open it again, the batch I started 10 seconds ago is still there, still ticking

## Acceptance Criteria

### `importBatchesProvider`

1. New Riverpod provider at `app/lib/features/recipes/add_recipe/state/import_batches_provider.dart` (or the project's conventional state location — match the existing pattern for app-level state)
2. Provider exposes `AsyncValue<ImportBatchesState>` where `ImportBatchesState` holds:
   - `List<ImportBatch> active` — batches with `status` in `{pending, submitted, running, partial}`
   - `List<ImportBatch> recentlyCompleted` — batches that transitioned to `{succeeded, failed}` within the last 5 minutes (kept around so the user sees the "finished" beat before they disappear)
3. Provider polls `GET /v1/parser/batches?active=true&limit=20` on a **5-second interval** while the app is foregrounded and at least one batch is in a non-terminal state
4. When no batches are active, the provider falls back to a **30-second interval** so it still picks up batches the user may have started from another device
5. Provider exposes an **imperative `refresh()` method** the photo capture screen calls immediately after `POST /v1/parser/batches` returns, so the new batch appears in the strip within one frame (no waiting for the next 5s tick)
6. Provider exposes a `justStartedBatchIds: Set<String>` — IDs remain in this set for **3 seconds** after first appearing, then are auto-removed. Used by the UI to highlight freshly-submitted batches.
7. Provider cleans up its polling timer on `dispose` / when no listeners remain
8. Polling is paused when the app lifecycle transitions to `paused` / `inactive` and resumed on `resumed` (use `WidgetsBindingObserver` or the Riverpod equivalent)

### `ImportBatch` Data Model (Client)

9. New Dart model `app/lib/features/recipes/add_recipe/models/import_batch.dart`:
   ```dart
   class ImportBatch {
     final String id;
     final String status;
     final int groupCount;
     final DateTime createdAt;
     final DateTime? completedAt;
     final String? errorMessage;
     final List<ImportBatchJob> jobs;
     final List<ImportBatchImportJob> importJobs;
   }
   class ImportBatchJob {
     final String id;
     final String status;
     final String inputS3Key;
     final int groupIndex;
     final String? extractedText;
     final String? errorMessage;
   }
   class ImportBatchImportJob {
     final String id;
     final String status;
   }
   ```
10. Matches the response shape of `GET /v1/parser/batches/{id}` from story 13.12

### In-Progress Strip UI

11. New widget `ImportBatchesStrip` in `app/lib/features/recipes/add_recipe/widgets/import_batches_strip.dart`
12. The widget is embedded into `add_recipe_sheet.dart` near the top of the sheet content, **above** the existing import-type buttons, so the user sees it the moment they open "Add Recipe"
13. When there are **zero** active or recently-completed batches, the widget renders **nothing** (no empty state — don't waste sheet real estate)
14. When there is at least one batch, the widget renders a compact header (`In progress`) and a vertical list of batch rows
15. Each batch row shows:
    - Left: source-type icon (photo for now; extensible later)
    - Middle: a progress pill + human label based on status:
      - `submitted` / `running` with some jobs still `pending|running` → amber/blue "Reading text X/Y"
      - `running` with all jobs `succeeded` and import jobs in `processing` → "Structuring recipe"
      - `running` with at least one import job in `awaiting_review` → "Ready to review" (blue, tappable)
      - `succeeded` → green check "Ready to review" (tappable, navigates to the first `awaiting_review` item)
      - `partial` → amber warning "N of M recipes ready" (tappable)
      - `failed` → red error "Failed" with expandable error details
    - Right: a disclosure arrow (chevron) that expands the row
16. Expanding a row reveals the **debug affordance**: a list of the batch's parser jobs, each showing input filename (or last S3 key segment), its own status, and a **"Show extracted text"** toggle that reveals `extractedText` verbatim in a monospaced scrollable container. This is the "click more to see text" Leo asked for.
17. A freshly-submitted batch (id in `justStartedBatchIds`) renders with a subtle pulse / accent border for ~3 seconds, then settles into its normal row state
18. Tapping a row whose status is `succeeded` or has any `awaiting_review` import job navigates to `ImportReviewListScreen` for the most recent such import job
19. Tapping a `failed` row shows inline error details; no destructive retry in this story (future work)
20. Recently-completed rows auto-dismiss themselves from the strip **5 minutes** after `completed_at`. The user doesn't have to manually clear them.

### Non-Duplication with Activity Screen

21. The strip does **NOT** show past/archived imports — it is strictly active + recently completed. Full history remains the domain of the existing `import_history_screen.dart` / `activity_screen.dart` "Needs Review" section.
22. When a batch's import job reaches `awaiting_review`, the existing Needs Review section on the Activity screen picks it up automatically (already wired via story 13.9 / 13.10). No duplication of data, no forked truth — the strip polls batches, Activity polls import jobs.

## Technical Approach

### Riverpod Provider Skeleton

```dart
@riverpod
class ImportBatches extends _$ImportBatches {
  Timer? _pollTimer;
  final Set<String> _justStarted = {};
  final Map<String, DateTime> _justStartedAt = {};

  @override
  Future<ImportBatchesState> build() async {
    ref.onDispose(() => _pollTimer?.cancel());
    _schedulePoll();
    return _fetch();
  }

  Future<void> refresh() async {
    final fresh = await _fetch();
    state = AsyncData(fresh);
    _schedulePoll();
  }

  void markJustStarted(String batchId) {
    _justStarted.add(batchId);
    _justStartedAt[batchId] = DateTime.now();
    Future.delayed(const Duration(seconds: 3), () {
      _justStarted.remove(batchId);
      _justStartedAt.remove(batchId);
      if (state.hasValue) state = AsyncData(state.value!);
    });
  }

  Future<ImportBatchesState> _fetch() async { /* call listParserBatches */ }
  void _schedulePoll() { /* 5s if active, 30s if idle */ }
}
```

### Wiring into `add_recipe_sheet.dart`

At the top of the sheet's `build` method's Column children (after the drag handle and title, before the import-type buttons):

```dart
Consumer(
  builder: (context, ref, _) {
    final batches = ref.watch(importBatchesProvider);
    return batches.when(
      data: (s) => ImportBatchesStrip(state: s),
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  },
),
```

### Hook from `photo_capture_screen.dart`

Right after `createParserBatch` returns successfully (story 13.13's submit handler), before popping the screen:

```dart
ref.read(importBatchesProvider.notifier).markJustStarted(batchId);
await ref.read(importBatchesProvider.notifier).refresh();
```

(This requires `PhotoCaptureScreen` to be a `ConsumerStatefulWidget`. If it isn't already by end of 13.13, convert it here.)

### App Lifecycle

Use `AppLifecycleListener` (Flutter 3.13+) registered inside the provider's `build` to pause/resume the polling timer.

## Files Affected

**New:**
- `app/lib/features/recipes/add_recipe/state/import_batches_provider.dart`
- `app/lib/features/recipes/add_recipe/models/import_batch.dart`
- `app/lib/features/recipes/add_recipe/widgets/import_batches_strip.dart`

**Modified:**
- `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart` — embed the strip at the top
- `app/lib/features/recipes/add_recipe/photo_capture_screen.dart` — call `markJustStarted` + `refresh` on successful submit (tiny change, assumes 13.13 has landed)
- `app/lib/core/services/api_client.dart` — reuse `listParserBatches` from 13.13; no new methods here

## Out of Scope

- WebSocket / push-based live updates — polling is sufficient and much simpler
- Retrying failed batches from the strip (future story)
- Cancelling an in-flight batch from the strip (future story)
- Showing batches from other import types (URL bulk, PDF, spreadsheet) in the strip — only photo batches exist in 13.12. The strip is designed to handle any future batch source, but no other source is wired yet.
- Persisting recently-completed batches across app restarts — if the user kills the app, the "recently completed" list rebuilds from the next poll (active only). Acceptable tradeoff.

## Dependencies

- **Blocks on 13.12** — requires `GET /v1/parser/batches` endpoints
- **Blocks on 13.13** — `photo_capture_screen.dart` must call `markJustStarted` on successful submit, and the new `ImportBatch` shape matches 13.12's response
