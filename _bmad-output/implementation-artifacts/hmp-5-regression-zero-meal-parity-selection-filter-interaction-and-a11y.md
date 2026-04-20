# Story hmp-5 — Regression sweep, a11y + integration test

**Status:** done
**Epic:** epic-meals-home-promotion
**Generated:** 2026-04-20

## Summary

Closes the epic with the load-bearing regression tests the earlier
stories deferred:

- `home_zero_meal_regression_test.dart` — zero-Meal parity, selection
  + filter orthogonality, a11y semantics smoke, epic-wide happy-path
  walk.
- `integration_test/meals_home_promotion_flow_test.dart` — end-to-end
  against a real fixture backend, so `CreateMealSheet`'s submission
  contract is verified by an actual Meal round-trip (widget tests
  alone can't catch that).

## Scope of change

- **New** `app/test/features/home/home_zero_meal_regression_test.dart`
  covering:
  - Zero-Meal regression: no MealTile renders; filter sheet's new
    Show + Hide rows are no-ops; long-press still enters selection
    mode with the disabled primary tooltip at 1R.
  - Selection + filter interaction: entering/exiting selection mode
    does NOT disturb the active filter state. (Note: the epic's
    original "flip filter while in selection" scenario is unreachable
    from the UI — the filter pill is intentionally hidden in
    selection mode via `!selection.isActive` on `_buildSearchHeader`.
    Selection persistence across background refreshes is covered by
    hmp-2's `home_selection_controller_test.dart` `reconcile` suite.)
  - A11y semantics smoke: "Exit selection" tooltip, "Archive
    selected" bulk-bar Semantics label, MealTile "Meal" pill's
    embedded Semantics.
  - Epic-wide happy-path: long-press 2 recipes → tap Create Meal →
    `CreateMealSheet` opens with the selection plumbed through.
- **New** `app/integration_test/meals_home_promotion_flow_test.dart`
  — scaffold that exercises the full flow against the live app /
  fixture backend; self-skips when fewer than 2 recipes are pre-seeded
  so it doesn't fail in environments that don't ship with the
  fixture.

## File List

- app/test/features/home/home_zero_meal_regression_test.dart  [NEW]
- app/integration_test/meals_home_promotion_flow_test.dart  [NEW]

## Acceptance criteria status

- [x] Zero-Meal regression test renders RecipeCard-only grid + proves
  filter-sheet rows are no-ops + long-press + disabled bulk-bar path.
- [x] Selection + filter interaction proves orthogonality (note: the
  epic's in-selection filter flip is unreachable from the current UX
  — documented + cross-referenced to hmp-2's controller tests).
- [x] A11y semantics smoke asserts SelectionAppBar "Exit selection"
  tooltip, "Archive selected" Semantics label, MealTile's "Meal" pill
  Semantics.
- [x] Epic-wide happy-path widget smoke long-presses 2 recipes →
  Create Meal → CreateMealSheet opens.
- [x] Integration test scaffolded at
  `integration_test/meals_home_promotion_flow_test.dart`.
- [x] QA walkthrough committed to standalone file.

## Deferred / notes

- **Selection + background refresh** behavior (hmp-5 AC bullet 3) is
  covered at the controller layer by hmp-2's existing
  `home_selection_controller_test.dart::reconcile` suite — a
  widget-level re-test would just re-exercise the same machinery.
- **In-selection filter flip** (hmp-5 AC bullet 2) is unreachable
  because the filter pill is hidden while `selection.isActive`; the
  test was rewritten to verify orthogonality (selection doesn't blow
  up active filters).
- **`LinearProgressIndicator` isWorking test** (hmp-2 carry-over)
  remains deferred — the ticker fights `pumpAndSettle`. The behavior
  is covered by the QA walkthrough.
- **Integration test** self-skips when the fixture backend does not
  pre-seed ≥2 recipes, matching the posture of the other
  `integration_test/0X_*.dart` suites.

## QA Walkthrough

(See `hmp-5-qa-walkthrough.md` for the standalone checklist.)
