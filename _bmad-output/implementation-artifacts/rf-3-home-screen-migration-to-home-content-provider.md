# rf-3 — HomeScreen migration to homeContentProvider

**Status**: done
**Epic**: epic-reactive-foundation-home-imports

## What shipped

Home grid now consumes `homeContentProvider` — a `FutureProvider.autoDispose<HomeContent>` with `ref.keepAlive()` — instead of imperative `_loadRecipes()`/`_loadHomeContext()` in `initState`. The provider subscribes to the MutationBus internally and calls `ref.invalidateSelf()` when a recipe or meal event fires; pull-to-refresh calls `ref.refresh(homeContentProvider.future)` (user-intent, Locked Decision #2).

Filter/sort state stays local (pfc-4 zero-network filter guarantee preserved). Optimistic-mutation paths (favorite, meal-favorite, bulk-archive) continue to operate on local mirror state; the provider's refetch reconciles them on the next bus event.

## Files

- `app/lib/features/home/providers/home_content_provider.dart` — new. Fans out books → per-book recipes → favorites → meals → today's event → recently-cooked; merges `is_favorite` + `kind` tags; tolerates missing `SharedStateService` registration (best-effort App Group mirror).
- `app/lib/features/home/home_screen.dart` — rewritten initial-load path. Removed `initState` API calls, `_loadRecipes`, `_loadHomeContext`, `_loadAllRecipesFromBooks`, `_loadMealsForHome`, `_tagMeal`, `_isLoading`, `_error`, `_errorDetail`. Added `ref.listen<AsyncValue<HomeContent>>(homeContentProvider, ...)` → `_applyHomeContent(...)`. Loading/error render from the AsyncValue directly (with a `_hasContent` guard for the loading-flicker UX — epic AC #5).
- `app/lib/core/state/README.md` — updated canonical subscribe shape. `ref.listen<Stream<MutationEvent>>(mutationBusProvider, ...)` doesn't fire for a stable-instance `Provider<Stream>`; correct shape is `ref.read(mutationBusProvider).listen(...)` + `ref.onDispose(sub.cancel)`.
- `app/test/features/home/home_screen_reactivity_test.dart` — new regression test. Pump Home with `[Alpha]`, emit `RecipeCreated('r-b')`, assert `Bravo` visible without pull-to-refresh, no shimmer flash. Second test: `PantryItemCreated` does NOT refetch the grid (filter opt-in).
- `app/test/features/home/home_screen_test.dart` — updated fakes for the new provider's fetch surface (`listMeals`, `getRecipeBook`).

## Gotchas

- **`ref.listen<Stream<MutationEvent>>(mutationBusProvider, ...)` is a no-op** for the rf-1 bus because the stream instance never changes. The `ref.read(...).listen(...)` shape is the only one that actually subscribes. The README example was wrong in rf-1; fixed here.
- **`syncRecipeBooks` is best-effort.** Test harnesses that don't register `SharedStateService` no longer tank the home load — the provider swallows a missing registration and continues. Production path unchanged.
- **Loading-flicker guard** (`_hasContent` bool): keeps the previous grid visible during a MutationBus-driven refetch (Riverpod's default `AsyncLoading` transition would flash the skeleton).
- **Bulk-handler call sites** (`_handleCreateMeal`, `_handleAddToMeal`, `_handleArchive`) now call `ref.invalidate(homeContentProvider)` instead of `_loadRecipes()`.

## QA walkthrough

### Regression (CI-guarded)

- [x] `home_screen_reactivity_test.dart`: RecipeCreated → grid refreshes (`Alpha` + `Bravo` rendered, exactly 2 fetches).
- [x] `home_screen_reactivity_test.dart`: PantryItemCreated → no extra fetch (filter opt-in).
- [x] `home_filter_no_refetch_test.dart` (pfc-4): filter flip keeps fetch counters pinned at 1.
- [x] All 83 tests in `app/test/features/home/` green.

### Manual dogfood

- [ ] Cold-start app → Home renders within 800ms of the first network settle.
- [ ] Pull-to-refresh → spinner shows; grid re-renders; filter state unchanged.
- [ ] Paste URL → Save Recipe → pop to Home → new tile visible without pull-to-refresh. (Needs rf-4 emit to be end-to-end; today the mutation still goes through the legacy imperative path.)
- [ ] Flip meal-type filter → zero new network calls (`nx serve` logs or browser devtools).
- [ ] Airplane-mode → error state shows with ErrorBanner + Retry button; Retry restarts the fetch.
