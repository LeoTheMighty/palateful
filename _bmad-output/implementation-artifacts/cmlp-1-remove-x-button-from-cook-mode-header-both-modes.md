# cmlp-1 — Remove X button from cook-mode header (both modes)

Status: done

## Summary

Back arrow is now the sole exit affordance in cook mode. The redundant
`Icons.close` IconButton is gone from both `CookModeScreen` and
`MealCookModeScreen`. Header outer padding tightened from `symmetric(8, 4)`
to `fromLTRB(8, 4, 12, 4)` so the overflow menu doesn't hug the right edge.

## Changes

- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — removed the
  `IconButton(Icons.close, _exitCookMode)` between cooking-time and overflow;
  updated header container padding.
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart` —
  same removal + padding tweak in the meal-mode header builder.
- `app/test/cook_mode_resume_test.dart` — rewrote the "overflow menu is the
  rightmost header icon" test to compare `Icons.more_vert` vs.
  `Icons.schedule` (cooking-time badge) since the close icon no longer
  exists; added a `findsNothing` assertion on `Icons.close` in the header.

## Acceptance criteria

- `find.byIcon(Icons.close)` in the cook-mode header subtree returns
  nothing (both recipe + meal mode). ✓ (asserted in
  `cook_mode_resume_test.dart` `overflow menu is the rightmost header icon`).
- Back button (`Icons.arrow_back`) is the sole exit affordance. Overflow
  menu's Reset-cook entry still works. ✓ (no changes to back-button or
  overflow wiring).
- `cook_mode_resume_test.dart`'s overflow-rightmost test is rewritten to
  compare `Icons.more_vert` right-edge vs. `Icons.schedule` right-edge. ✓.
- The `StepTimerChip.onClose` callback test in `cook_mode_timer_test.dart`
  (line 181) continues to refer to an unrelated `Icons.close`. ✓ (no
  changes to that test file).

## File list

Modified:
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
- `app/test/cook_mode_resume_test.dart`
