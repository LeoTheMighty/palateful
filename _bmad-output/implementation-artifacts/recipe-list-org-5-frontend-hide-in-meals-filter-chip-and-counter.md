# recipe-list-org-5 — Frontend: hide-in-meals filter chip + counter

**Epic:** `epic-recipe-list-organization`
**Status:** done
**Order in epic:** 5 of 6

## Goal

Promote the "hide recipes attached to a Meal" filter from a hidden
toggle inside the bottom sheet to a default-ON chip rendered above
the recipe list (home + book detail). The chip carries a counter
that reads either "*N recipes · M hidden in meals*" or "*N recipes ·
M shown in meals*" depending on filter state. When the filter empties
the list (everything is in a meal), a celebratory empty state offers
a one-tap path to disable the filter.

## Scope — files this story touches

**NEW**
- `app/lib/features/home/widgets/hide_in_meals_chip.dart` — the chip
  + the celebratory empty state widget
  (`HideInMealsEmptyState`).
- `app/test/features/home/hide_in_meals_chip_test.dart` — chip copy
  + interaction + empty-state coverage.

**MODIFY**
- `app/lib/features/home/widgets/filter_bottom_sheet.dart` — remove
  the `SwitchListTile` for hide-components (the chip replaces it).
  Flip `HomeFilterState.defaults.hideComponentsOfMeals` to `true`.
- `app/lib/features/home/home_screen.dart` —
  - `_hideComponentsOfMeals` initial flipped to `true`.
  - Mount `HideInMealsChip` above the recipe grid via
    `_buildHideInMealsChip()`. Hidden during selection mode.
  - Branch `_buildRecipeGrid` to render `HideInMealsEmptyState`
    when the filter is the *cause* of the empty list (otherwise the
    generic "no recipes" state would mislead).
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` —
  - Add `_hideInMeals: true` field.
  - Mount the chip above the grid; empty state when the filter
    empties the list.
  - Add `_filteredRecipesForRender()` helper that applies vibe +
    hide-in-meals. Uses `is_in_meal` per-row when the Story 2
    backend payload provides it, falls back to `_meals` component
    lookup otherwise.
  - Add `_hiddenInMealsCount()` helper preferring the Story 2
    `total_in_meals` response field.
- `app/test/features/home/filter_bottom_sheet_show_type_test.dart` —
  drop the removed-toggle assertions; flip default expectations.
- `app/test/features/home/home_filter_hide_components_test.dart` —
  drive the chip instead of the bottom-sheet toggle; expectations
  updated for the default-ON behavior.
- `app/test/features/home/home_zero_meal_regression_test.dart` —
  reword the "filter sheet rows" test to drive the chip.
- `app/test/features/home/home_bulk_actions_test.dart` — the
  "selecting only already-in-Meal recipes" test now disables the
  hide chip first so the in-meal recipe is visible to long-press.

## Acceptance criteria

1. **Chip renders above the list in both views** (home grid +
   table; book-detail grid + table). Hidden during selection mode
   on home so the bulk bar surface is unobstructed.
2. **Default ON.** A fresh app start hides recipes attached to any
   meal in both surfaces.
3. **Counter copy mirrors state.**
   - Active: `"N recipes · M hidden in meals"` (or `"N recipes"`
     when M = 0).
   - Inactive: `"N recipes · M shown in meals"` (or `"N recipes"`
     when M = 0).
   - Singular noun for `N == 1`.
4. **Tap toggles state and updates copy.** Counts re-derive in the
   same frame; no network call fires.
5. **Empty state.** When the filter is ON and every recipe in this
   surface is attached to a meal, render `HideInMealsEmptyState` —
   a celebratory icon + copy + a "Show all recipes" button that
   disables the filter.
6. **Bottom-sheet redundancy removed.** The previous "Hide components
   of Meals" `SwitchListTile` is gone — the chip is the single
   surface. `HomeFilterState.defaults.hideComponentsOfMeals` is now
   `true` so Clear-All matches the chip's default.
7. **Coverage.** 7 new chip widget tests cover all four (active,
   meals present/absent) × (singular/plural noun) copy variants
   plus the tap dispatch and the empty-state CTA.

## Implementation notes

- **Two parallel state vars (one per screen).** Home uses its
  existing `_hideComponentsOfMeals`; book-detail introduces
  `_hideInMeals`. They're the same UX semantically but live on
  different state objects — keeping them parallel avoids cross-
  screen coupling and matches how the existing vibe filter
  duplicates between the two screens.
- **Backend payload preferred where available.** Book-detail's
  `_hiddenInMealsCount()` reads `total_in_meals` from the Story 2
  response; if missing (rolling deploy / older API), it falls back
  to per-row `is_in_meal` flags, then finally to the `_meals`
  component union. Home derives counts purely from the loaded
  meals' `component_recipe_ids` (no list endpoint there yet).
- **Empty-state predicate is "filter caused this".** `_recipes.isEmpty`
  alone could mean "no recipes at all" or "filter hides everything".
  The empty-state branch checks that **at least one recipe exists**
  AND **every recipe is in a meal** before showing the celebratory
  state. Otherwise the generic "no recipes yet" empty state still
  fires.
- **Default flip is intentionally a breaking change.** The four
  existing tests that depended on hide=false-by-default were
  updated, not worked around. The user-facing impact (recipes-in-
  meals are tidied by default) is exactly the epic's central UX
  bet.
- **`_draftHideComponents` stays in the bottom sheet state object**
  so the round-trip is preserved (the chip writes to home state →
  the bottom sheet sees it via `initialState` → carries it back
  through `onApply`). The user just doesn't have a control for it
  in the sheet anymore.

## Tests added

`test/features/home/hide_in_meals_chip_test.dart` — 7 cases:
- active + meals present → "N recipes · M hidden in meals"
- inactive + meals present → "N recipes · M shown in meals"
- active + no meals → "N recipes"
- inactive + no meals → "N recipes"
- singular noun for N = 1
- tap fires `onTap`
- empty state renders + the show-all CTA dispatches

## Tests updated (existing → new behavior)

- `filter_bottom_sheet_show_type_test.dart` — drops the toggle row
  assertion; flips `isDefault` expectations to reflect hide=true
  default.
- `home_filter_hide_components_test.dart` — drives the chip; the
  "1 Meal with 2 components" case asserts the components are hidden
  *by default*, then toggles the chip to expose all.
- `home_zero_meal_regression_test.dart` — exercises the chip
  instead of the removed bottom-sheet toggle.
- `home_bulk_actions_test.dart` — disables the chip in the
  "selecting in-meal recipes" test so the in-meal recipe is
  long-pressable.

## File list

- NEW `app/lib/features/home/widgets/hide_in_meals_chip.dart`
- MODIFY `app/lib/features/home/widgets/filter_bottom_sheet.dart`
- MODIFY `app/lib/features/home/home_screen.dart`
- MODIFY `app/lib/features/recipe_books/recipe_book_detail_screen.dart`
- NEW `app/test/features/home/hide_in_meals_chip_test.dart`
- MODIFY `app/test/features/home/filter_bottom_sheet_show_type_test.dart`
- MODIFY `app/test/features/home/home_filter_hide_components_test.dart`
- MODIFY `app/test/features/home/home_zero_meal_regression_test.dart`
- MODIFY `app/test/features/home/home_bulk_actions_test.dart`
- MODIFY `_bmad-output/implementation-artifacts/sprint-status.yaml`
