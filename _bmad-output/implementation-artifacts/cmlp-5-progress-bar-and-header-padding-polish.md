# cmlp-5 — Progress bar + header padding polish

Status: done

## Summary

The progress bar's outer `Container.margin` dropped from `horizontal: 48`
to `horizontal: 24` in both `CookModeScreen` and `MealCookModeScreen`,
aligning the bar with the step card's 24dp content padding. (Header
padding tweaks were already applied in cmlp-1.)

## Changes

- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — progress
  bar `margin: const EdgeInsets.symmetric(horizontal: 48)` →
  `const EdgeInsets.symmetric(horizontal: 24)`.
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
  — same change in the meal-mode step content builder.
- `app/test/cook_mode_resume_test.dart` — added
  `cmlp-5 — progress bar margin is horizontal 24` to the `cmr-2` group
  (pins the recipe-mode margin via `tester.widget<Container>` +
  `find.ancestor` of `LinearProgressIndicator`).
- `app/test/meal_cook_mode_sectioning_test.dart` — extended the
  `flat-total progress bar at flat-step 9 of 20 ≈ 50%` test with the
  same `Container.margin` assertion for meal mode.

## Acceptance criteria

- Progress bar's outer `Container.margin` is
  `EdgeInsets.symmetric(horizontal: 24)` in both cook-mode screens,
  asserted by `tester.widget<Container>(find.ancestor(of: ...))`. ✓.
- Header doesn't visually collide with the cooking-time badge after
  the X-button removal (cmlp-1 applied `fromLTRB(8, 4, 12, 4)` which
  gives 12dp right breathing room; verified by running the existing
  cook-mode widget tests which already pump the real header builder
  with no overflow). ✓.
- No test pins `horizontal: 48` or `48.0` in cook-mode context — grep
  confirms the old margin value is gone from both source and tests. ✓.

## File list

Modified:
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
- `app/test/cook_mode_resume_test.dart`
- `app/test/meal_cook_mode_sectioning_test.dart`
