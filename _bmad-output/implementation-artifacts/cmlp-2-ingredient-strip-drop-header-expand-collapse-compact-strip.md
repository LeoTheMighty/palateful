# cmlp-2 — Ingredient strip: drop header + Expand/Collapse + compact strip + empty guard

Status: done

## Summary

The `IngredientStrip` now always renders its grouped-grid expanded
layout directly. The header row (INGREDIENTS label, `x/y` counter,
Expand/Collapse `GestureDetector`), the `AnimatedCrossFade` wrapper,
the `_buildHorizontalStrip` horizontal scroll path, and the
`isCompact` branch inside `_IngredientChip` are all gone. When
`ingredients.isEmpty`, the widget returns `SizedBox.shrink()` — no
padding, no header scaffold.

## Changes

- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`
  — rewrote `_IngredientStripState.build()`: early-return on empty list,
  then return `_buildExpandedGrid()` directly (no header, no
  `AnimatedCrossFade`, no `AnimatedContainer`). Deleted
  `_buildHorizontalStrip` + compact branch in `_IngredientChip`.
  Recipe-mode outer padding bumped from `fromLTRB(16, 0, 16, 16)` to
  `fromLTRB(16, 12, 16, 16)` to restore top breathing room that the
  deleted header used to provide.
- `app/test/cook_mode_test.dart` — rewrote the cmm-1 AC7 test to assert
  group keys render on initial mount (no Expand tap required); dropped
  the `--- From X ---` text assertions from here (cmlp-4 will replace
  that rendering). Added `expect(find.text('Expand'), findsNothing)` +
  `Collapse` + `INGREDIENTS`. Added new empty-ingredient test that
  asserts `SizedBox.shrink` output. Updated
  `IngredientStrip renders ingredient names` to use
  `find.textContaining(...)` since the chip now renders
  `quantity + unit + name` as one Text (cmlp-3 will split them).
- `app/test/meal_cook_mode_ingredients_test.dart` — removed the
  compact-view source-tag test, removed the 10-grapheme truncation
  test (no chip-level tag exists to truncate). Rewrote
  `expanded view: group dividers` as `grouped view: group keys render
  on initial mount`, dropping the `tester.tap(find.text('Expand'))`
  call. Kept the 1-component-no-tag test, dropped its Expand tap.
- `app/test/cook_mode_gesture_test.dart` — deleted the
  `IngredientStrip expand/collapse button has at least 64dp height`
  test (no Expand button exists); also removed the unused
  `ingredient_strip.dart` import from the file.
- `app/test/cook_mode_resume_test.dart` — the first `cmr-2` test tapped
  `find.text('Ingredient 1')`. The chip now renders the combined
  `"1 cup Ingredient 1"` string, so updated to
  `find.textContaining('Ingredient 1')`. Chip no longer overflows when
  checked (the compact vertical chip was the source of the pre-existing
  ~7px overflow); the `tester.takeException()` drain is kept as a
  defensive measure.

## Acceptance criteria

- `find.text('INGREDIENTS')` / `find.text('Expand')` / `find.text('Collapse')`
  return `findsNothing` in cook-mode tests. ✓ (asserted in
  `cook_mode_test.dart` + `meal_cook_mode_ingredients_test.dart`).
- `find.byType(AnimatedCrossFade)` inside the cook-mode subtree returns
  `findsNothing`. ✓ (AnimatedCrossFade is no longer instantiated).
- Empty-ingredient edge case: mounting
  `IngredientStrip(ingredients: const [], ...)` renders zero size. ✓
  (new test in `cook_mode_test.dart`).
- `cook_mode_test.dart:246–294`, `meal_cook_mode_ingredients_test.dart:91–171`,
  and `cook_mode_gesture_test.dart:161–192` are updated / deleted per
  the epic. ✓.
- Ingredient list visible on initial mount without any tap. ✓ (always
  expanded).

## File list

Modified:
- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`
- `app/test/cook_mode_test.dart`
- `app/test/meal_cook_mode_ingredients_test.dart`
- `app/test/cook_mode_gesture_test.dart`
- `app/test/cook_mode_resume_test.dart`
