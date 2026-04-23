# cmlp-2 — QA walkthrough

## Setup
- Build app from the current `main`. No env vars.
- Sign in; need one recipe with ≥ 5 ingredients and one recipe with 0
  ingredients (temporarily removing the ingredient list in the editor
  is fine).

## Smoke 1 — Full ingredient list visible on mount (~30s)
1. Open a recipe with ≥ 5 ingredients. Tap "Start Cooking".
2. Cook mode opens. **The full ingredient list is visible immediately**
   — no Expand button, no `INGREDIENTS` ALL-CAPS header, no `x / y`
   counter.
3. Scroll the outer view up/down — the ingredient list scrolls
   naturally as part of the step column. Tall lists push the step card
   below the fold (accepted trade-off).

## Smoke 2 — Empty ingredient list renders nothing (~20s)
1. Open a recipe with 0 ingredients (or remove all ingredients from one
   for the test). Tap "Start Cooking".
2. Cook mode opens. **No ingredient-strip region** is visible — no empty
   header, no "0 ingredients" label, no blank padding band. The step
   card sits directly under the active-timers row / header.

## Smoke 3 — Ingredient tapping still toggles checked state (~30s)
1. In cook mode with ≥ 3 ingredients, tap an ingredient chip.
2. The chip flips to the `cookCompleted` background with strike-through
   on its text (plus a check icon) — same behaviour as today.
3. Tap again — unchecks.

## Smoke 4 — Meal cook mode: old `--- From ... ---` dividers still render
Note: cmlp-4 will replace these dashed-text dividers with typographic
group headers; cmlp-2 only removes the Expand/Collapse gate.

1. Open a 2+ recipe meal, Start Cooking.
2. Ingredient strip shows ingredients grouped by component, with
   `--- From <Name> ---` dashed-text dividers visible on mount (no
   Expand tap needed). cmlp-4 will polish these.

## Automated coverage
- `flutter test test/cook_mode_test.dart` — pass, including new
  empty-list test and updated Expand/Collapse absence assertions.
- `flutter test test/meal_cook_mode_ingredients_test.dart` — pass.
- `flutter test test/cook_mode_gesture_test.dart` — pass
  (expand-button 64dp test deleted).
- `flutter test test/cook_mode_resume_test.dart` — pass (ingredient
  tap target adjusted for combined-text chip).
- `flutter test test/cook_mode_timer_test.dart` — pass.

## Sign-off
Story ships when all four smokes above show no regression and the
automated suites are green.
