# cmp-4 — Step completion untoggle on back-navigation

**Status:** review
**Epic:** epic-cook-mode-polish

## Summary

Fixes the dogfood regression where stepping back still rendered the
prior step with a green check in the pill strip. `_goToStep(step)`
now removes `step` from `_completedSteps` whenever `step <
_currentStep`. Forward navigation via `_nextStep` is unchanged — it
keeps adding the departing step to the set.

All three back-nav paths in `cook_mode_screen.dart` funnel through
`_goToStep`:

1. **Swipe-right** (`onHorizontalDragEnd`) → `_previousStep` → `_goToStep(_currentStep - 1)`
2. **Left-zone tap** (`onTapUp` left 25%) → `_previousStep` → `_goToStep(_currentStep - 1)`
3. **StepNavigator pill-tap** → `_goToStep(index)` directly

Testing `_goToStep` via a minimal state harness + a StepNavigator pill
tap covers all three (cmp-4 AC8). The pill at the current index never
renders a check icon — `step_navigator.dart` gates the completed
visual on `index != currentStep` (cmp-3 addition, reinforced here).

## Tests

New test group in `app/test/cook_mode_gesture_test.dart`:
`Back-navigation untoggles completed state (cmp-4)`, 4 cases:

- advance 0→4, pill-tap back to 2 → `{0, 1, 3}`
- advance 0→4, pill-tap back to 0 → `{1, 2, 3}`
- pill at currentStep never shows a check regardless of set membership
- Semantics labels (`Step N, current|completed|upcoming`) are emitted

## File list

- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — `_goToStep` untoggle
- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart` — `excludeSemantics: true` + `container: true` on pill `Semantics` so the label is not merged with inner GestureDetector semantics
- `app/test/cook_mode_gesture_test.dart` — new test group + `_BackNavHarness`
