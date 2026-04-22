# rf-5 — ImportHistoryScreen + Imports tab + activity badge reactivity

**Status**: done
**Epic**: epic-reactive-foundation-home-imports

## What shipped

Import-item mutations (dismiss, retry, dismissAll) now emit `MutationEvent`s; `importsSeeAllProvider` and `ActivityReadProvider` subscribe to the bus and refetch/recompute eagerly instead of waiting on the 30s poll tick.

Per epic Locked Decision #1 note, the emits live directly in the widget handlers — there is no `ImportItemService` today. This is the one explicit exception to the service-layer-emit rule in the epic; flagged as cleanup debt in the Risks section.

## Files

- `app/lib/core/state/mutation_bus.dart` — added `mutationBusStream()` top-level helper for non-Riverpod subscribers (getIt services).
- `app/lib/features/activity/import_history_screen.dart` — `_dismissSingleItem`, `_dismissAllFailed`, `_retrySingleItem` each emit `ImportItemDismissed` / `ImportJobDismissed` / `ImportItemRetried` on server 200. Catch-blocks route to `showMutationFailureSnackbar` (Design Principle #6); existing `_loadAttentionView()` fallback stays for rollback.
- `app/lib/features/activity/imports_tab.dart` — live surface. `_archiveItem` emits `ImportItemDismissed`; `_retryItem` emits `ImportItemRetried`.
- `app/lib/features/activity/providers/imports_see_all_provider.dart` — `ImportsSeeAllNotifier.build()` subscribes to the bus; filters to `ImportItemDismissed | ImportItemRetried | ImportJobDismissed`; calls `refreshFromTop()` if the section has already loaded. Subscription canceled via `ref.onDispose`.
- `app/lib/features/activity/providers/activity_read_provider.dart` — constructor subscribes to the bus; on import events calls `refreshUnreadCount()`. Added `dispose()` to cancel the subscription in tests.
- `app/test/features/activity/import_history_reactivity_test.dart` — new. 6 tests:
  - importsSeeAllProvider: dismiss event → one refetch after first load.
  - importsSeeAllProvider: retry event with section closed → no-op.
  - importsSeeAllProvider: RecipeCreated never triggers.
  - ActivityReadProvider: ImportItemDismissed → refreshUnreadCount fires.
  - ActivityReadProvider: ImportJobDismissed → refreshUnreadCount fires.
  - ActivityReadProvider: RecipeCreated → no refresh.

## Gotchas

- **`ActivityReadProvider` is a getIt singleton, not a Riverpod provider** — it subscribes via `mutationBusStream()` (non-Riverpod handle), cached in `_busSub`, disposed via new `dispose()`. Production never calls `dispose()` (process lifetime); tests must call it in `tearDown`.
- **See-all refetch is gated on `hasLoadedFirstPage`** — if the user hasn't opened the section yet, an import event is a no-op. Prevents wasted fetches on background events. First open still triggers its own fetch.
- **`_archiveItem` in ImportsTab is the live dismiss path**; `_dismissSingleItem` in ImportHistoryScreen is the deprecated surface still reachable for one release cycle. Both emit the same event type.
- **The backend dismiss response is expanded in rf-2** (item/jobDismissed in body). The dismiss emit picks up the shape when present; falls back to `item: null` / `jobDismissed: false` when the server is still on the legacy shape. Subscribers treat the absence as "just invalidate".
- **Bell badge poll stays**. rf-5 is additive — the 30s `Timer.periodic` covers cold-start + partner-WS-missed states; the bus covers instant local reactivity. Confirmed by epic AC #4 ("double path is intentional").

## QA walkthrough

### Regression (CI-guarded)

- [x] `import_history_reactivity_test.dart` — 6 new tests green.
- [x] All 130 `flutter test test/features/activity/` tests green (existing poll-based tests untouched).

### Manual dogfood

- [ ] Open Activity Hub → Imports tab → swipe-dismiss a failed item → snackbar shows "Dismissed"; bell badge decrements within one frame (no 30s wait).
- [ ] Expand See-all footer → archived items list → swipe-dismiss one elsewhere → See-all refetches and the new archived row appears at the top.
- [ ] Retry a failed import → snackbar "Retrying"; bell badge recomputes on server 200.
- [ ] Offline → swipe-dismiss → Snackbar: "Couldn't dismiss, try again"; row restores.
- [ ] Clear all failed in deprecated ImportHistoryScreen route → all rows vanish; one ImportJobDismissed emits; bell badge drops by N.
