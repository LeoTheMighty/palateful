# rmc-2 — Used-in-these-Meals reactivity on Recipe detail

**Status**: done
**Epic**: epic-reactive-migration-meals-calendar

## What shipped

`MealsUsingThisRecipe` widget lifted from `StatefulWidget + FutureBuilder` to `ConsumerWidget + ref.watch(usedInMealsProvider)`. The new provider (`FutureProvider.family.autoDispose<List<MealSummary>?, String>`) subscribes to the bus and invalidates on:

- **Narrow path**: `MealComponentAdded | MealComponentRemoved` where `event.recipeId == recipeId` → immediate `invalidateSelf()`.
- **Coarse path**: `MealArchived | MealUnarchived | MealUpdated` (any meal) → 100ms debounced `invalidateSelf()`. Any referenced meal's summary can change its name or archive flag, and the cross-lookup result is derived, so the list still needs to refetch — but one debounce window protects against a meal-update storm.

Load-bearing md-6 invariant preserved: empty / error → `SizedBox.shrink()` (no header, no empty state). The widget now also uses an `AsyncValue.value` guard to keep the previous list visible during refetch (no shimmer flash).

Public recipe screen (`public_recipe_screen.dart`) is untouched and still doesn't mount this widget — privacy invariant unchanged.

## Files

- `app/lib/features/recipes/providers/used_in_meals_provider.dart` — **new**. Family provider keyed by `recipeId`, fetches via `MealService.listMealsUsingRecipe`, subscribes to the bus with a narrow + debounced-coarse filter. Timer cancelled on dispose.
- `app/lib/features/recipes/widgets/meals_using_this_recipe.dart` — converted to `ConsumerWidget`. Kept `_ShimmerRow`, `_MealsRow`, `_MealCard` subwidgets as-is (load-bearing render output unchanged). Added `AsyncValue.value` previous-data guard for no-flicker refetches.
- `app/test/features/recipes/meals_using_this_recipe_test.dart` — harness updated to register `MealService` (the provider reads it via `getIt`) + wrap router in `ProviderScope`. All 5 existing scenarios (zero / 1 / N meals, error, loading-shimmer) still pass.
- `app/test/features/recipes/used_in_meals_reactivity_test.dart` — **new**. Three scenarios:
  1. `MealComponentAdded(recipeId match)` → immediate refetch, new meal visible, list count jumps from 1 → 2.
  2. `MealComponentAdded` for a different recipeId → NO refetch (narrow filter).
  3. Three `MealUpdated` events within 100ms → debounced to exactly one refetch after the window closes.

## Gotchas

- **AsyncValue `.value` not `.valueOrNull` in Riverpod 3.0.** The type is nullable (`List<MealSummary>?`) so `.value` returns `List<MealSummary>??` collapsed to `List<MealSummary>?`. Works fine for the previous-data flicker guard.
- **Coarse path is necessary, not redundant.** Without it, archiving a meal that contained `recipeId` wouldn't invalidate the cross-lookup (the emit carries `mealId` + `bookId` only, no `recipeId`). The 100ms debounce absorbs the worst case (partner typing notes across N meals) without introducing a bulk event type.
- **`autoDispose` is correct here.** The widget only mounts on recipe detail; unmounting tears down the provider + subscription + timer. No keepAlive needed — a stale `recipeId` → Meals cache that outlives the screen isn't valuable.
- **Test harness needed a `ProviderScope` wrapper.** The original `StatefulWidget` didn't use Riverpod; the migration means every test that pumps this widget must wrap in `ProviderScope`. `_pumpTarget` already does this — one-line change.
- **`MealService` also needs to be registered in every test.** The provider uses `getIt<MealService>()` instead of constructing one inline. `_registerFakes` now registers both.

## QA walkthrough

### Regression (CI-guarded)

- [x] `meals_using_this_recipe_test.dart` — all 5 scenarios pass:
  - zero meals hides entirely;
  - 1 meal shows "Used in 1 meal" singular;
  - N meals shows plural header + all tiles;
  - fetch error hides the section;
  - loading renders shimmer (no header).
- [x] `used_in_meals_reactivity_test.dart` — 3 scenarios pass:
  - MealComponentAdded(recipeId match) → immediate refetch + new tile visible;
  - MealComponentAdded for a different recipeId → no refetch;
  - 3 MealUpdated in 100ms → exactly one debounced refetch.
- [x] All 105 meal tests + 359 total in recipes/meals/home still green — no regressions.

### Manual dogfood (end-to-end — deferred to rmc-5)

- [ ] Open recipe detail for a recipe referenced by 2 meals → "Used in 2 meals" row renders.
- [ ] From another device / another tab, add that recipe as a 3rd component of a new meal → recipe detail row flips to "Used in 3 meals" within one frame of the server 200, no pull-to-refresh.
- [ ] Remove the recipe from one of the meals → row drops back to 2.
- [ ] Archive a referenced meal → row drops back to fewer (or hides entirely at zero) within ~100ms of the event.
