# Story hmp-3 — Bulk actions: Create Meal + Add to Meal + Archive wiring, partial-failure pattern

**Status:** in-progress
**Epic:** epic-meals-home-promotion
**Generated:** 2026-04-20

## Summary

Swap the three stub handlers (`_handleCreateMealStub` / `_handleAddToMealStub`
/ `_handleArchiveStub`) on `home_screen.dart` for real dispatches:

- **Create Meal** → opens `CreateMealSheet` with the selection's recipe
  ids as `initialComponents` and the first-selected recipe's book.
- **Add to Meal** → client-side dedup against `meal.componentRecipeIds`,
  parallel per-recipe `addRecipeToMeal` dispatch with per-call result
  collection, shared partial-failure snackbar + dialog.
- **Archive** → confirmation dialog, parallel `bulkArchiveRecipes` + per-
  Meal `archiveMeal` dispatch, same partial-failure surface.

New helper `bulk_dispatcher.dart` isolates the pure parallel-dispatch +
result-collection + error-reason logic so it can be unit-tested without
a widget tree. New widget `bulk_partial_failure_dialog.dart` renders the
failure list shared by Add-to-Meal + Archive.

## Scope of change

- **New**: `home/widgets/bulk_dispatcher.dart` — `BulkOperation` enum,
  `BulkOperationResult`, `explainBulkError`, `runBulkOperations<T>`.
- **New**: `home/widgets/bulk_partial_failure_dialog.dart` — shared
  dialog for Add-to-Meal + Archive partial/full-fail paths.
- **Modified**: `home_screen.dart`:
  - Replaces the three stub handlers with real dispatches.
  - Adds `_isBulkOperating` flag → passed into `HomeBulkActionBar.isWorking`.
  - Uses `MealService.addRecipeToMeal`, `MealService.archiveMeal`, and
    `ApiClient.bulkArchiveRecipes` directly.
  - Calls `ref.read(homeSelectionProvider.notifier).exit()` on success
    + invalidates provider caches + reloads the grid.
- **Tests**:
  - `bulk_dispatcher_test.dart` — `runBulkOperations` collects success
    + failure rows; `explainBulkError` maps the DioException / typed
    exception paths.
  - `bulk_partial_failure_dialog_test.dart` — dialog renders one row per
    failure, skips successes, titles per operation.
  - `home_bulk_create_meal_test.dart` — long-press 2 recipes + tap
    "Create Meal" opens `CreateMealSheet` with the right components +
    bookId/bookName.
  - `home_bulk_add_to_meal_test.dart` — dedup on already-present
    recipes short-circuits to the "All selected" snackbar; partial
    failures surface the dialog; success emits the snackbar.
  - `home_bulk_archive_test.dart` — confirm cancel aborts with no
    dispatch; confirm accept fires the parallel archive path; partial
    failure surfaces the dialog.

## File List

- app/lib/features/home/home_screen.dart  [MODIFIED]
- app/lib/features/home/widgets/bulk_dispatcher.dart  [NEW]
- app/lib/features/home/widgets/bulk_partial_failure_dialog.dart  [NEW]
- app/test/features/home/bulk_dispatcher_test.dart  [NEW]
- app/test/features/home/bulk_partial_failure_dialog_test.dart  [NEW]
- app/test/features/home/home_bulk_create_meal_test.dart  [NEW]
- app/test/features/home/home_bulk_add_to_meal_test.dart  [NEW]
- app/test/features/home/home_bulk_archive_test.dart  [NEW]

## Acceptance criteria status

- [x] Create Meal opens CreateMealSheet with initialComponents in
  selection order + bookId/bookName from the first-selected recipe.
- [x] Add to Meal dedupes against the target Meal's existing component
  recipe ids; empty-after-dedup short-circuits with the "All selected"
  snackbar and exits selection mode with no API call.
- [x] Add to Meal parallel dispatch collects per-call results without
  eager error; snackbar text adapts to all-success / partial / all-fail.
- [x] Archive shows confirmation with "N recipe(s) and M Meal(s)" copy
  scaled for recipe-only / meal-only / mixed selections. Cancel aborts
  cleanly.
- [x] Archive parallel dispatches `bulkArchiveRecipes` + per-Meal
  `archiveMeal` and merges results into one partial-failure row list.
- [x] `BulkPartialFailureDialog` lists each failed item by display name
  + error reason. Successful rows are never shown.
- [x] `isWorking` flag disables every bulk-bar button and renders the
  thin linear progress indicator while any dispatch is inflight.
- [x] Provider invalidations: `invalidateMeal(ref, mealId, bookId: …)`
  after Add-to-Meal; `_loadRecipes()` after Archive + Add + Create.
- [x] Widget/unit tests covering dispatcher helpers, dialog, and each
  of the three home handlers.

## Deferred / notes

- `LinearProgressIndicator` widget testing for `isWorking=true` is still
  deferred (hmp-2 carry-over) — the ticker fights `pumpAndSettle`. The
  behavior is covered by the isBulkOperating state flag in the archive
  + add-to-meal tests plus the QA walkthrough.

## QA Walkthrough

1. Long-press Kale Salad, tap Lemon Dressing. Bulk bar: Create Meal
   enabled. Tap Create Meal → `CreateMealSheet` opens with both recipes
   pre-filled, name pre-populated "Kale Salad + Lemon Dressing", book
   chip "Dinners." Tap Create → sheet dismisses, selection clears,
   grid reloads with the new Meal tile.
2. Long-press Kale Salad Meal, tap Miso Broccoli. Bar: `Add to "Kale
   Salad Meal"` enabled. Tap → snackbar "Added 1 recipe to Kale Salad
   Meal." Selection clears. Meal tile's chip row updates to include
   Miso Broccoli.
3. Long-press a Meal that already contains a recipe, then long-press
   that recipe too. Tap Add to Meal → snackbar "All selected recipes
   are already in this Meal." No API call fires.
4. Select 3 recipes on a Meal where 1 is already a component → Add to
   Meal only hits the API for the 2 new ones; snackbar "Added 2
   recipes to …".
5. Force a 403 on one of the add-recipe calls (admin/permissions) →
   snackbar "Added 1 of 2 — see details" with a View action that opens
   the dialog listing the failed recipe + "You can't edit this recipe."
6. Select 5 recipes + 1 Meal. Tap Archive. Dialog: "Archive 5 recipes
   and 1 Meal? You can restore them later from Archive." Cancel →
   nothing happens, selection intact. Accept → snackbar "Archived 6
   items." Selection clears; both recipes and the Meal vanish from the
   grid; they appear in the Archive tab.
7. Force a failure on one Meal archive → snackbar "Archived 5 of 6 —
   see details" with View listing the failed Meal + "Conflict — try
   again." Selection clears on dialog dismiss; grid is reloaded.
8. While any dispatch is in flight, bulk-bar buttons are disabled and
   a thin progress indicator renders at the top of the bar.

## Gotchas for next stories

- `bulk_dispatcher.dart` lives under `features/home/widgets/` so hmp-4 /
  hmp-5 can import it directly without crossing feature boundaries.
- `BulkOperation.addToMeal` vs `BulkOperation.archive` drives the error-
  reason strings; if a sibling epic adds a third bulk surface (e.g.
  bulk-favorite), extend the enum here, not inline in the calling code.
- `CreateMealSheet.show(...)` takes `bookName` as a required positional
  arg — if the first-selected recipe's book name is missing (shouldn't
  happen — home merges it into `_recipes` via `_loadAllRecipesFromBooks`),
  the handler bails silently. The defensive branch is untested but
  guarded; document in hmp-5's regression sweep if it becomes reachable.
