# Story hmp-4 — Home filter extensions: Show type + Hide components of Meals

**Status:** done
**Epic:** epic-meals-home-promotion
**Generated:** 2026-04-20

## Summary

Extend `HomeFilterState` with two new client-side filter axes:

- `showType: ShowTypeFilter` (`all | recipesOnly | mealsOnly`) —
  radio-style chips in a new **Show** section between Sort by and
  Meals.
- `hideComponentsOfMeals: bool` — `SwitchListTile` row right below the
  Show chips; hides any recipe whose id sits in any Meal's
  `component_recipe_ids`. Meals themselves are never hidden.

Both plumb through `FilterBottomSheet.onApply`, are applied **after**
the recipe/meal merge inside `home_screen.dart`, contribute to the
FilterPill's active-dot state, and are reset alongside the existing
fields by Clear all (+ restored by Undo).

## Scope of change

- **Modified**: `filter_bottom_sheet.dart`:
  - `HomeFilterState` gains `showType` + `hideComponentsOfMeals`
    fields with defaults `all` / `false`.
  - `isDefault` now includes both new fields.
  - Sheet renders a **Show** section + `_ShowTypeChipWrap` + a
    `SwitchListTile` toggle (keyed
    `ValueKey('hide-components-of-meals-toggle')`).
  - Clear all resets both new drafts.
- **Modified**: `home_screen.dart`:
  - New `_showTypeFilter` + `_hideComponentsOfMeals` fields.
  - New `_applyKindFilters(List<dynamic>, List<dynamic> meals)` runs
    after `_mergeRecipesAndMeals` (the zero-meal path is bit-identical
    to pre-epic — zero meals means zero component ids).
  - `_openFilterSheet` pipes both new fields into + out of the sheet.
  - `_showClearAllUndo` restores both.
  - FilterPill `isActive` computation includes both new fields via
    `HomeFilterState.isDefault`.
- **Tests**:
  - `filter_bottom_sheet_show_type_test.dart` — sheet renders the new
    controls, Apply flows state, Clear all resets, isDefault table.
  - `home_filter_hide_components_test.dart` — full-stack home render:
    zero-meal no-op; 1 Meal / 2 components hides both recipes; Meals-
    only hides all recipes keeping the Meal.

## File List

- app/lib/features/home/home_screen.dart  [MODIFIED]
- app/lib/features/home/widgets/filter_bottom_sheet.dart  [MODIFIED]
- app/test/features/home/filter_bottom_sheet_show_type_test.dart  [NEW]
- app/test/features/home/home_filter_hide_components_test.dart  [NEW]

## Acceptance criteria status

- [x] `HomeFilterState.showType` + `hideComponentsOfMeals` fields
  added with the right defaults.
- [x] FilterBottomSheet renders the new Show section between Sort by
  and Meals, plus the Hide-components toggle row right below it.
- [x] `onApply` emits both new fields; `_openFilterSheet` picks them
  up on the home screen.
- [x] `_applyKindFilters` applied after the recipe+meal merge;
  `showType` filters by kind; `hideComponentsOfMeals` filters recipes
  whose id is in any Meal's component list.
- [x] FilterPill shows the active dot when either new field is
  non-default.
- [x] Clear all resets both new fields + Undo restores them.
- [x] Widget tests cover the sheet + the end-to-end home render.

## Deferred / notes

- The chip wrap uses the shared `_SheetFilterChip` widget so the Show
  row has the same tap + visual grammar as Meals / Vibes. No
  accessibility-specific labels added here — hmp-5's a11y sweep will
  verify the SwitchListTile + chips announce correctly.

## QA Walkthrough

1. Open home. Tap the filter pill → sheet opens. Confirm **Show**
   section renders between Sort by + Meals. Confirm the three chips
   read "All / Recipes only / Meals only." Confirm a **Hide components
   of Meals** SwitchListTile is right below, default OFF with subtitle
   "Hide recipes that are part of any Meal."
2. Tap "Meals only" → Apply. Grid filters to Meal tiles only. Filter
   pill's active dot shows.
3. Reopen → tap "All" → Apply. All tiles back.
4. Toggle **Hide components of Meals** ON → Apply. Recipes that are
   components of any Meal disappear from the grid; the Meals stay;
   uncombined recipes stay. Active dot shows.
5. Tap filter pill → tap Clear all → Apply. Snackbar "Sort & filters
   cleared" with Undo. Grid returns to full (both new filters reset).
6. Tap Undo before it fades → sheet's state restores (sort + meal +
   showType + hide-components all back to pre-clear values).
7. With zero Meals in the fixture: toggle Hide Components ON → Apply.
   Grid unchanged (no component ids to filter against). Active dot
   still reflects non-default state.

## Gotchas for next stories

- `_applyKindFilters` runs after `_mergeRecipesAndMeals`; the meals
  list passed in is the ORIGINAL fetched list, not the filtered grid
  — the hide-components component-id set must always come from every
  Meal on home, not just the visible ones.
- The SwitchListTile has `key: ValueKey('hide-components-of-meals-toggle')`
  for test-id stability; hmp-5's integration test uses it too.
- `_ShowTypeChipWrap` reuses `_SheetFilterChip` (private to
  filter_bottom_sheet.dart). If hmp-5's a11y sweep decides to swap it
  for `FilterChip`, add Semantics around it rather than rewriting.
