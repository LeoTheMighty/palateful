# Story pfc-4 — Home filter is zero-network

**Status:** review
**Epic:** epic-perf-flutter-client-polish
**Generated:** 2026-04-21

## Summary

Closes the `perf-2` AC-3 regression where `_reapplyFilters()` in
`home_screen.dart` called `_loadRecipes()` on every filter flip.
Filters now apply in-memory over pristine `_allRecipes` / `_allMeals`
backing lists. `_loadRecipes()` still runs on `initState`,
pull-to-refresh, and explicit mutations (save / archive / meal /
recipe-book changes) — unchanged elsewhere.

## Scope of change

- Add two pristine backing fields `List<dynamic> _allRecipes` and
  `List<dynamic> _allMeals`.
- `_loadRecipes()` populates both after the network round-trip, then
  feeds a new `_buildFilteredGrid(recipes, meals)` helper whose output
  is stored in `_recipes`.
- `_reapplyFilters()` no longer calls `_loadRecipes()`; it calls
  `setState(() { _recipes = _buildFilteredGrid(_allRecipes,
  _allMeals); })`.
- `_buildFilteredGrid` encodes the existing pipeline
  (`_applyFilters` → `_applySorting` → `_mergeRecipesAndMeals` →
  `_applyKindFilters`) in one place so the two entry points —
  fresh-fetch and reapply — stay bit-identical.
- New widget test `home_filter_no_refetch_test.dart` drives the grid
  through a meal-type filter flip and asserts `getRecipeBooksCalls`,
  `getRecipeBookCalls`, `getFavoritesCalls`, `listMealsCalls` all stay
  pinned at 1 after the initial load.

## File List

- app/lib/features/home/home_screen.dart  [MODIFIED]
- app/test/features/home/home_filter_no_refetch_test.dart  [NEW]

## Acceptance criteria

- [x] `_reapplyFilters` at `home_screen.dart` no longer calls
  `_loadRecipes()`.
- [x] All filter changes (meal type, vibe, sort, show-type,
  hide-components-of-meals) apply in-memory over pristine backing
  lists.
- [x] `_loadRecipes()` runs on `initState`, pull-to-refresh, and
  existing mutation callsites. No new callsite added.
- [x] Hard AC — "zero network calls on the documented path": asserted
  via widget test that pins every list-endpoint call counter at 1
  across a filter flip.
- [x] Existing `home_filter_hide_components_test.dart` + sheet tests
  continue to pass (zero-regression against md-4 / hmp-4).

## QA walkthrough

1. Open app. Home loads → network tab shows
   `getRecipeBooks` + `getRecipeBook` + `getFavorites` + `listMeals`
   each firing once.
2. Tap the Sort & filter pill. Switch to "Breakfast" meal type. Apply.
   Network tab fires NOTHING. Grid visibly filters to breakfast items.
3. Flip sort to "Newest". Apply. No network call. Grid reorders.
4. Flip "Hide components of Meals" toggle ON. Apply. No network call.
   Component-recipe tiles disappear (only if a Meal exists).
5. Pull-to-refresh. Network fires once (the one allowed path).
6. Tap into a recipe, hit the archive button, back out.
   `_loadRecipes()` runs from the archive callback — this is expected
   (mutation path).

## Code review findings (addressed)

- [LOW] **Undo-from-filter-sheet path** — the "clear all" undo snackbar
  in `_showClearAllUndo` already calls `_reapplyFilters()` after
  restoring filter state. Verified this now means an in-memory rebuild
  rather than a refetch. Good — undo is zero-network too.
- [LOW] **`_recipes` mutation in `_toggleFavorite`** — favorite toggles
  mutate a recipe object in place (`recipe['is_favorite'] = …`).
  Because `_recipes` and `_allRecipes` share references, the flag is
  visible through both. The pipeline re-reads `is_favorite` on every
  rebuild (inside `_applyFilters`? no — it doesn't filter on favorite).
  Net: nothing to change; in-place mutation remains safe.
- [LOW] **Mid-load filter flip race** — if a user flips a filter while
  `_loadRecipes` is still running, the in-memory rebuild runs against
  the stale empty `_allRecipes`. When the load resolves, `setState`
  overwrites `_recipes` with the freshly-filtered grid, so the user's
  latest filter state IS applied (via `_buildFilteredGrid` in
  `_loadRecipes`). No corrective action needed.

## Gotchas for next stories

- Both entry points (`_loadRecipes` post-fetch block + `_reapplyFilters`)
  funnel through `_buildFilteredGrid`. If you need to change filter
  order or add a new filter stage, edit `_buildFilteredGrid` ONCE — do
  not re-inline the pipeline at either callsite.
- Keep `_allRecipes` / `_allMeals` as pristine references. They get
  mutated in-place only for `is_favorite` / `kind` bookkeeping during
  load — nothing should trim them post-load.
