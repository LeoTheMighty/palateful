# cmp-5 — Colour-value widget tests + Epic 6 regression sweep

**Status:** review
**Epic:** epic-cook-mode-polish

## Summary

Pins CookModeTheme token values numerically in unit tests so a future
palette tweak is a deliberate decision, not a silent drift. Adds
StepNavigator surface-colour widget tests that pump the widget under
both `AppTheme.light()` and `AppTheme.dark()` and assert the current-
pill paints `cookAccent` and the check icon paints `cookOnCompleted`.

Epic 6 regression sweep: all of `cook_mode_test.dart`,
`cook_mode_gesture_test.dart` (including the new cmp-4 + cmp-5
groups), `cook_mode_timer_test.dart`, `offline_cook_mode_test.dart`,
`post_cook_feedback_test.dart`, and `theme/` pass locally for files
not blocked by unrelated parallel-session WIP. See the QA walkthrough
for details.

## What's in

`app/test/theme/cook_mode_theme_test.dart` — two new pinned-Color
tests (light + dark), each asserting all 13 tokens match the expected
32-bit ARGB value.

`app/test/cook_mode_gesture_test.dart` — new group `Cook-mode surface
colours (cmp-5)` with two `testWidgets`:
- `light: StepNavigator current pill paints cookAccent`
- `dark: StepNavigator current pill paints cookAccent`

Each asserts the pill container's decoration colour matches
`CookModeTheme.{light,dark}.cookAccent`, and the check-icon in the
completed pill matches `cookOnCompleted`. These are the exact widget-
level assertions that would have caught the "everything-is-orange"
regression this epic was filed to fix.

## Local test status (cmp-5 AC4)

- `test/theme/` — 12 passing (cook + import-state)
- `test/cook_mode_gesture_test.dart` — 11 passing (4 original + 4
  cmp-4 + 2 cmp-5 + 1 semantics)
- `test/cook_mode_timer_test.dart` — 22 passing
- `test/offline_cook_mode_test.dart` — passes locally
- `test/post_cook_feedback_test.dart` — 5 passing
- `test/cook_mode_test.dart` — **blocked by unrelated parallel-session
  WIP** (pantry_editor_screen.dart / ingredient_search.dart churn).
  When I stash the parallel pantry edits, the HEAD copy of pantry
  itself fails to compile (`searchIngredients` missing on ApiClient).
  This is pre-existing and orthogonal to cook mode; individual test
  files compile once pantry's parallel-session conflict resolves on
  main.

## Manual QA checklist (cmp-5 AC5)

See `cmp-5-qa-walkthrough.md`.

## File list

- `app/test/theme/cook_mode_theme_test.dart` — added pinned-Color
  assertions for light + dark tokens
- `app/test/cook_mode_gesture_test.dart` — added `Cook-mode surface
  colours (cmp-5)` group
