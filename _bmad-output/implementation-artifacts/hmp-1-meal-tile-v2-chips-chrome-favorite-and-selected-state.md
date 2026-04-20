# Story hmp-1 — MealTile v2: component chips, accent chrome, favorite overlay, selected-state

**Status:** done
**Epic:** epic-meals-home-promotion
**Generated:** 2026-04-20

## Summary

Rewrites `MealTile` with a 2-px accent border, a top-left "Meal" pill
(`Icons.layers_outlined` + drop shadow), a component-name chip row that
resolves names client-side via a caller-supplied `componentNameResolver`,
a favorite-star overlay that matches `RecipeCard`, and a selection-mode
checkmark overlay for hmp-2.

Also ships a strictly-additive backend field — `component_recipe_ids` on
`MealSummaryResponse` — so the Flutter client has ids to feed into the
client-side join. The draft epic assumed this field existed; it did not.
This is the epic's documented escape-hatch (hmp-0) shipped inline.

## Scope of change

- Backend: `MealSummaryResponse.component_recipe_ids: list[str]` added,
  populated from `MealService.hydrate_components` in order.
- Flutter: `MealSummary.componentRecipeIds` parses the new field.
- Flutter: `MealTile` rewritten — new props `componentNameResolver`,
  `isFavorited`, `onFavoriteToggle`, `selected`. "N recipes" decorative
  badge retired. Backward-compat: callers that pass no resolver still
  render "(N recipes)" in the chip row so no caller loses information.
- Flutter: `home_screen.dart` wires `componentNameResolver`,
  `isFavorited` from `favorited_meals`, and optimistic
  favorite/unfavorite dispatch with error rollback.
- Tests: `meal_tile_test.dart` rewritten (16 cases) + one backend
  assertion added to `test_meal_router.py`.

## File List

- services/api/src/schemas/meal.py  [MODIFIED]
- services/api/src/api/v1/meal/_response.py  [MODIFIED]
- services/api/tests/test_meal_router.py  [MODIFIED]
- app/lib/features/meals/models/meal.dart  [MODIFIED]
- app/lib/features/meals/widgets/meal_tile.dart  [MODIFIED — full rewrite]
- app/lib/features/home/home_screen.dart  [MODIFIED]
- app/test/features/meals/meal_tile_test.dart  [MODIFIED — extended]

## Acceptance criteria status

- [x] 2-px accent border (uses `colorScheme.primary` @ 0.6 alpha; no new
  theme token introduced — decision: keep change scoped to this widget;
  introduce `MealAccent` token in a follow-up if another surface adopts
  the chrome).
- [x] Top-left "Meal" pill with `Icons.layers_outlined` + drop shadow.
- [x] Component-chips row: 0/1/2/3/5 cases render as spec'd; archived
  fallback appends `· (archived)` ONCE.
- [x] Constructor gains `componentNameResolver`, `isFavorited`,
  `onFavoriteToggle`, `selected`. All optional (backward-compat).
- [x] "N recipes" decorative badge retired; fallback "(N recipes)" when
  no resolver supplied.
- [x] Favorite star overlay + `onFavoriteToggle` tap; home wires
  optimistic update + rollback.
- [x] Selected-state checkmark overlay.
- [x] Widget tests cover every bullet.
- [x] Zero-regression: book-detail + search-results pass no resolver,
  fall back to "(N recipes)". Both compile and the existing
  `meal_tile_test.dart`-baseline tests were rewritten for v2.

## QA Walkthrough

1. Open home grid. Any existing Meal tile should now show:
   - 2-px accent border around the card.
   - Translucent "Meal" pill with `Icons.layers_outlined` top-left of the
     collage hero. Pill has a soft drop shadow.
   - Below the meal name: a single line of component names separated by
     `· ` — e.g. "Kale Salad · Lemon Dressing". If >2 components, trails
     with ` · +N`.
   - If any component can't be resolved (archived recipe etc.):
     `· (archived)` once at the end.
   - Favorite star top-right, mirroring recipe tiles.
2. Tap the favorite star on a Meal tile. Heart fills immediately
   (optimistic); snackbar-free success. Tap again — heart empties,
   carousel drops the Meal. With network off, wait for failure — the
   heart rolls back to its prior state.
3. Tap the tile body. Should still navigate to `/meals/:id`.
4. Open a recipe book detail screen that contains a Meal. The MealTile
   there should render unchanged — no resolver is provided, so the chip
   row shows "(N recipes)" (same count information the old badge had).
5. Zero-Meal state: home has no Meals → no MealTile in the grid; no
   visual regression. Book detail with no Meals → grid shows recipes
   only, unchanged.

## Gotchas for next stories

- `MealSummaryResponse` now carries `component_recipe_ids`. hmp-3 + hmp-4
  read this client-side (hmp-3's Add-to-Meal dedup; hmp-4's
  Hide-components-of-Meals filter). Do NOT invent a second path to
  fetch component ids — reuse this one.
- `home_screen.dart` maintains `_favoriteMealIds: Set<String>` from
  `/favorites`.favorited_meals. Any new meal-tile wire-up should consume
  that set, not call `/favorites` a second time.
- `MealTile.selected: bool` is wired through but home hasn't passed it
  yet — hmp-2 flips that on.
- Parallel /dev loop: `services/api/tests/test_add_meal_to_shopping_list.py`
  was failing in the dirty working tree when we started — the failure
  is unrelated to hmp-1 (it's from the in-flight ingredient-string
  simplification WIP). In clean isolation (only hmp-1 changes applied)
  all 94 meal-suite tests pass. Do not spend cycles chasing it here.
