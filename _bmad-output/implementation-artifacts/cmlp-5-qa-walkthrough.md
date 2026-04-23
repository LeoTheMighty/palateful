# cmlp-5 — QA walkthrough

## Setup
- Build app from the current `main`. No env vars.
- Open any recipe with ≥ 3 steps and any meal with 2+ components.

## Smoke 1 — Recipe cook mode progress bar alignment (~30s)
1. Start cooking a recipe.
2. The progress bar below the header sits aligned with the step card's
   content: its left edge matches the step card's left text edge, and
   its right edge matches the step card's right text edge.
3. Before cmlp-5 the bar was inset by 48dp on each side — too narrow;
   now it spans the full 24dp-padded content width.

## Smoke 2 — Meal cook mode progress bar alignment (~30s)
1. Start cooking a meal. Advance a few steps.
2. Same alignment check — bar edges match the step card's text edges.

## Smoke 3 — Top-of-screen chrome (~1 min, dogfood only)
- Header: back arrow · recipe/meal name · timer · cooking-time · overflow.
- Active-timers row (if any).
- Ingredient strip (group headers + chips for meals; flat Wrap for
  recipes; nothing if the list is empty).
- Progress bar.
- Step card.
- No double-padded gap at any join; nothing clips the screen edge.

## Smoke 4 — iPhone SE / Pixel 6 size classes (~2 min, optional)
- Same recipe + meal on narrower / taller devices; bar stays aligned.

## Automated coverage
- `flutter test test/cook_mode_resume_test.dart` — pass, includes new
  `cmlp-5 — progress bar margin is horizontal 24` test.
- `flutter test test/meal_cook_mode_sectioning_test.dart` — pass,
  existing progress-bar test now also asserts margin.
- Full cook-mode regression pass (`cook_mode_test`, `meal_cook_mode_test`,
  `meal_cook_mode_ingredients_test`, `cook_mode_gesture_test`,
  `cook_mode_timer_test`) — green.

## Sign-off
Story ships when the smokes above look right on dogfood and the
automated suites are green.
