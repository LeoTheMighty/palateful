# rmc-1 — Meal mutation sites + meal providers reactivity

**Status**: done
**Epic**: epic-reactive-migration-meals-calendar

## What shipped

Every write method on `MealService` now emits a MutationBus event on the success branch of the API call (Locked Decision #1, service-layer emits). `mealsByBookProvider`, `mealsAllProvider`, `mealByIdProvider` subscribe to the bus and refetch / patch on matching events.

`mealByIdProvider` was lifted from `FutureProvider.family` to an `AsyncNotifierProvider.family` so the subscription can `state = AsyncData(...)` on payload-bearing events — detail screens patch in place without a refetch round-trip (AC #5). On `MealFavorited` / `MealUnarchived` with `meal == null`, the notifier falls back to `ref.invalidateSelf()`.

UI handlers in `meal_edit_screen.dart` / `meal_detail_screen.dart` route mutation-failure `catch` blocks through `showMutationFailureSnackbar(...)` with the new `MutationType` entries (`updateMeal` / `archiveMeal` / `favoriteMeal` / `unfavoriteMeal` / `reorderComponents` / `removeComponent` / `addComponent` / `shareMeal`). `create_meal_sheet.dart` already used its own inline `ErrorBanner` for mutation failures — no change needed there.

`archiveMeal`, `restoreMeal`, `favoriteMeal`, `unfavoriteMeal` all gained a required `bookId:` parameter — call sites in `meal_detail_screen`, `home_screen` (`_toggleMealFavorite`, `_ArchiveMealTarget`), and `archived_recipes_screen` pass it from the Meal / MealSummary they already hold.

## Files

- `app/lib/core/state/mutation_event.dart` — extended Meal stubs:
  - `MealCreated(mealId, meal, bookId)` — added `bookId` field.
  - `MealArchived(mealId, bookId)` — added `bookId`.
  - `MealUnarchived(mealId, bookId, meal?)` — new event; `meal` nullable so the slim-response backend path falls back to invalidate.
  - `MealFavorited(mealId, bookId, isFavorited, meal?)` — added `bookId` + made `meal` nullable for pre-rf-2 slim shape.
  - `MealComponentAdded(mealId, recipeId, meal)` — new.
  - `MealComponentRemoved(mealId, recipeId, meal)` — new.
  - `MealComponentsReordered(mealId, meal)` — new; distinct from `MealUpdated` per epic locked decision.
  - `MealShared(mealId, shareToken)` — stub for the sharing epic.
- `app/lib/core/state/mutation_failure_copy.dart` — added `createMeal`, `updateMeal`, `archiveMeal`, `unarchiveMeal`, `favoriteMeal`, `unfavoriteMeal`, `addComponent`, `removeComponent`, `reorderComponents`, `shareMeal` entries.
- `app/lib/features/home/providers/home_content_provider.dart` — extended `_shouldInvalidate` switch with `MealUnarchived`, `MealComponentAdded`, `MealComponentRemoved`, `MealComponentsReordered`.
- `app/lib/features/meals/services/meal_service.dart` — `createMeal`, `updateMeal`, `addRecipeToMeal`, `removeRecipeFromMeal`, `reorderMealComponents`, `archiveMeal`, `restoreMeal`, `favoriteMeal`, `unfavoriteMeal`, `share` all emit on success. `favoriteMeal`/`unfavoriteMeal`/`archiveMeal`/`restoreMeal` now take `bookId:` param. `favorite*` still returns `bool` for backward compat; the event carries the full Meal payload when the server returns one (post-rf-2), `meal: null` otherwise (pre-rf-2).
- `app/lib/features/meals/providers/meals_provider.dart` — `mealsByBookProvider` + `mealsAllProvider` subscribe to the bus. `mealByIdProvider` converted to `AsyncNotifierProvider.family<MealByIdNotifier, Meal, String>` for in-place patching. `invalidateMeal(...)` helper kept as a one-release shim (AC #6).
- `app/lib/features/meals/meal_detail_screen.dart` — `_toggleFavorite`, `_archiveMeal`, `_shareMeal` route through `showMutationFailureSnackbar`; pass `bookId` to service calls.
- `app/lib/features/meals/meal_edit_screen.dart` — `_saveNameDescription`, `_reorderComponents`, `_removeComponent`, `_addRecipe` route failures through `showMutationFailureSnackbar`.
- `app/lib/features/home/home_screen.dart` — `_toggleMealFavorite` now goes through `MealService` (not raw ApiClient) + passes `bookId`. `_ArchiveMealTarget` carries `bookId`. Dropped the now-unused `_apiClient` field + `api_client.dart` import.
- `app/lib/features/recipes/archived_recipes_screen.dart` — `_restoreMeal` passes `bookId`.
- `app/test/features/meals/meal_service_mutation_bus_test.dart` — **new**. 13 tests: every write method emits the right event subtype with the right payload, including bookId; `archiveMeal` does NOT emit on failure; favorite/unfavorite handle both post-rf-2 full-meal and pre-rf-2 slim shapes.
- `app/test/features/meals/meal_detail_component_reactivity_test.dart` — **new** (AC #9). `MealComponentAdded` patches Meal detail in place — asserts "Garlic Bread" chip appears without a refetch round-trip (getMealCalls pinned at 1). Second test: `MealFavorited(meal: null)` falls through to invalidate-refetch (getMealCalls → 2).
- `app/test/features/meals/meals_by_book_reactivity_test.dart` — **new** (AC #10). `mealsByBookProvider(book-a)` invalidates on `MealCreated(book-a)`; does NOT invalidate on `MealCreated(book-b)` or `RecipeCreated`; `MealComponentAdded` (no bookId) invalidates because list summary fields can change.
- `app/test/features/meals/meal_edit_screen_failure_snackbar_test.dart` — **new** (AC #7). `updateMeal` failure → "Couldn't update meal" toast + Retry action.
- `app/test/features/meals/meal_detail_screen_test.dart` — fake service updated for new signatures (`bookId:` param) + expected toast copy updated to `MutationType.favoriteMeal` + `MutationType.shareMeal` strings.
- `app/test/features/meals/meal_service_test.dart` — existing archive/restore/favorite test calls now pass `bookId`.

## Gotchas

- **`mealByIdProvider` is an `AsyncNotifierProvider.family` now, not a `FutureProvider.family`.** Call sites using `ref.watch(mealByIdProvider(id))` are unchanged (both yield `AsyncValue<Meal>`), but if any test was reading `.future` or peeking into the notifier-less API, it would need to adapt. None were doing so as of rmc-1.
- **Riverpod 3.0 `AsyncNotifier` family pattern**: there's no `FamilyAsyncNotifier<T, Arg>` class in this version. Instead extend `AsyncNotifier<T>` and take the arg via the constructor: `class MealByIdNotifier extends AsyncNotifier<Meal> { MealByIdNotifier(this.mealId); final String mealId; ... }` + register with `AsyncNotifierProvider.family<MealByIdNotifier, Meal, String>(MealByIdNotifier.new)`.
- **Widget viewport in detail tests**: the default `testWidgets` viewport is 800×600. A meal detail with 3+ components pushes the third row below the fold, so reactivity tests pin `tester.view.physicalSize = Size(1080, 2400)` (same trick `home_screen_reactivity_test.dart` uses) before `pumpWidget`.
- **Parallel /dev session had already extended `mutation_event.dart` + `mutation_failure_copy.dart`** for the books/profile/pantry migration epic. The rmc-1 additions to those files composed cleanly — the Meal-specific entries land in the same `git diff` hunks without conflicting with the books/profile/pantry additions. `sprint-status.yaml` line for this epic flipped from `backlog` to `in-progress` + `rmc-1` to `done` in the same commit.
- **Pre-rf-2 favorite slim-shape fallback**: `_emitFavorite` checks `payload.containsKey('components')` to distinguish a full `MealResponse` from the legacy `{is_favorite: bool}` shape. The test `favoriteMeal with legacy slim shape → meal=null, fallback path` pins the contract.
- **`invalidateMeal` is now a no-op-ish shim.** Service emits already trigger provider refetches. Call sites in `meal_edit_screen` / `meal_detail_screen` keep the helper invocations per AC #6 (backward compat); they'll be removed when the books/profile/pantry migration lands its grep sweep.
- **Share failure copy**: the old `meal_detail_screen` toast read "Couldn't generate share link. Try again." — migrated to `MutationType.shareMeal` → "Couldn't share meal". The existing test was updated to match.

## QA walkthrough

### Regression (CI-guarded)

- [x] `meal_service_mutation_bus_test.dart` — 13 tests, all green:
  - createMeal / updateMeal / addRecipeToMeal / removeRecipeFromMeal / reorderMealComponents / archiveMeal / restoreMeal (both shapes) / favoriteMeal (full + slim) / unfavoriteMeal / share each emit the expected subtype with the expected payload.
  - archiveMeal on API error emits NOTHING.
- [x] `meal_detail_component_reactivity_test.dart` — MealComponentAdded patches in place (getMealCalls stays at 1); MealFavorited(null) falls through to invalidate (getMealCalls bumps to 2).
- [x] `meals_by_book_reactivity_test.dart` — book-a event invalidates book-a; book-b event does NOT; RecipeCreated does NOT; MealComponentAdded (no bookId) does invalidate.
- [x] `meal_edit_screen_failure_snackbar_test.dart` — updateMeal failure routes through showMutationFailureSnackbar; "Couldn't update meal" + Retry.
- [x] All 105 tests in `app/test/features/meals/` green after update.
- [x] All 248 tests in `app/test/features/home/` + `app/test/features/recipes/` green — no regressions from the signature changes.

### Manual dogfood (deferred to rmc-5 end-to-end)

- [ ] Create Meal "Sunday Roast" (3 components) → pop to Home → tile visible without pull-to-refresh.
- [ ] Open Meal detail → Add Recipe → new chip appears without refresh.
- [ ] Archive a Meal from detail → Home tile vanishes in one frame.
- [ ] Tap heart on Meal detail with airplane-mode → "Couldn't favorite meal" toast + Retry; optimistic state rolls back.
