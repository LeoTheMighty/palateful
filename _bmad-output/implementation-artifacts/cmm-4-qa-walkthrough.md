# cmm-4 — QA walkthrough

This story wires the source-tagged ingredient strip in meal cook mode
and the stable-key check-state plumbing. cmm-5 layers in
component-aware timers; cmm-6 layers in the post-cook sheet; cmm-7
adds the Resume gate with the "Ingredients changed" drift snackbar.

## Setup
- Build the app from `main`.
- Need a 2-3-component meal with overlapping ingredients (e.g. two
  recipes that both use "1 cup flour" or "Salt").

## Smoke 1 — Source tags (compact view) (~1 min)
1. Open meal detail → tap Start Cooking → cook UI mounts.
2. The ingredient strip at the top (horizontal scroll) shows every
   ingredient from every component recipe.
3. Each chip carries a small tag chip below the name with the source
   component name (e.g. "Dressing", "Salad").
4. Long component names (>10 chars) get truncated with an ellipsis
   (e.g. "Grilled Ch…").

## Smoke 2 — Group dividers (expanded view) (~1 min)
1. Tap "Expand" in the ingredient strip header.
2. Ingredients now wrap into a grid view, grouped by component with
   horizontal-rule dividers reading `--- From Dressing ---`,
   `--- From Salad ---`, etc.

## Smoke 3 — No dedup (~1 min)
1. Use a meal whose components have overlapping ingredients (two
   "1 cup flour" rows, or two "Salt" rows).
2. Both should render as TWO chips (one per source component), each
   with its own source tag.

## Smoke 4 — Recipe cook regression (~1 min)
1. Open a single-recipe cook flow (NOT a meal cook).
2. Ingredient strip should render with NO source tag chips and NO
   group dividers in expanded view (pixel-identical to pre-meal cook).

## Negative
- No "Ingredients changed since your last session" snackbar (cmm-7).
- No multi-row post-cook sheet (cmm-6).

## Automated coverage
- `flutter test test/meal_cook_mode_ingredients_test.dart` — 9 tests
  covering: source-tagged plan, no-dedup, per-chip tag rendering,
  group dividers, 10-grapheme truncation, 1-component no-tags,
  stable-key drift handling, parity with backend iteration order.
- `flutter test test/cook_plan_test.dart` — stable-key contract.

## Sign-off
Story is shippable when smokes 1, 2, 3, 4 show no regression and the
automated suite is green.
