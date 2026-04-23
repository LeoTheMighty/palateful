# cmlp-4 — Meal mode: group headers + delete section header above step card

Status: done

## Summary

Meal cook mode's ingredient strip now emits a typographic group header
(`Dressing` at 13px w600, 0.4 letter-spacing, `cookOnSurface` alpha 0.7;
followed by a 1dp `cookDivider` alpha 0.5 rule) per source-component
group instead of the old `--- From <Name> ---` dashed-text divider.
The `RecipeSectionHeader` render site above the step card is gone.
The widget file `recipe_section_header.dart` stays on disk — its
deletion is deferred to `epic-cook-mode-multi-recipe-flow`.

## Changes

- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`
  — rewrote the meal branch of `_buildExpandedGrid`:
  - Each group renders as `Column(key: Key('ingredient_group_$rawTag'),
    children: [header, chips])`. Keys preserved for existing tests.
  - The header is a `Padding(fromLTRB(16, 16, 16, 4))` wrapping
    `Semantics(header: true, child: Column([Text(name, 13px w600),
    SizedBox(4), Divider(1dp cookDivider.alpha(0.5))]))`.
  - Untagged chips bucket into a group labelled `Other` — only emitted
    when the untagged set is non-empty (empty bucket renders nothing).
  - Outer wrapper collapsed to `Padding(bottom: 16)` — horizontal
    padding lives on each group's header + chip Wrap so the header
    divider spans the full content width.

- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
  — removed the `RecipeSectionHeader` render site (`showSectionHeader`
  local + the `if (showSectionHeader) ... RecipeSectionHeader(...)
  SizedBox(height: 8)` block) and removed the now-unused
  `import 'widgets/recipe_section_header.dart';`.

- `app/test/meal_cook_mode_sectioning_test.dart` — removed the
  `recipe_section_header.dart` import, dropped the first test in the
  `cmm-3` group (the `[7,4,9] plan: header reads "Dressing · 1 / 7"`
  test that called `tester.widget<RecipeSectionHeader>`), renamed the
  group to `cmm-3 — navigator boundaries + flat-total progress bar`.
  The navigator-boundary + progress-bar tests are preserved.

- `app/test/meal_cook_mode_ingredients_test.dart` — added
  `flutter/semantics.dart` import and three cmlp-4 tests:
  - `group headers render as "Dressing" / "Salad" / "Grilled Chicken"
    (no dashed dividers)` — asserts `findsOneWidget` on each group-name
    text, and `findsNothing` on `textContaining('--- From')` +
    `textContaining('--- Other')`.
  - `group header is a Semantics header node` — asserts
    `tester.getSemantics(find.text('Dressing')).hasFlag(SemanticsFlag.isHeader)`.
  - `untagged group renders as "Other"` — asserts the `Other` label
    plus the `ingredient_group_untagged` key.

## Acceptance criteria

- `find.text('Dressing')`, `find.text('Salad')`, `find.text('Grilled Chicken')`
  each `findsOneWidget` in the ingredient subtree; keys
  `ingredient_group_*` render. ✓.
- `find.textContaining('--- From ')` returns `findsNothing` across
  cook-mode tests. ✓ (asserted in `meal_cook_mode_ingredients_test.dart`
  and implicitly in every cook-mode test suite — the code path that
  produced the string is gone).
- The `cmm-3 — recipe section header` test group in
  `meal_cook_mode_sectioning_test.dart` that pinned
  `tester.widget<RecipeSectionHeader>` is deleted. The rest of the
  group (navigator-boundaries + flat-total progress-bar) stays. ✓.
- `find.byType(RecipeSectionHeader)` would return `findsNothing` in
  meal mode now (the import is gone from the screen file; the widget
  is never mounted). ✓.
- `"Dressing · 1 / 7"` string appears nowhere in cook-mode. ✓.
- Each group-header node carries `Semantics(header: true)`. ✓
  (new test asserts the flag).
- The `recipe_section_header.dart` file is NOT deleted — the
  multi-recipe epic owns that. ✓.

## File list

Modified:
- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
- `app/test/meal_cook_mode_sectioning_test.dart`
- `app/test/meal_cook_mode_ingredients_test.dart`

Intentionally not deleted (deferred to next epic):
- `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart`
