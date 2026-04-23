# cmlp-3 — QA walkthrough

## Setup
- Build app from the current `main`. No env vars.
- Sign in; need one recipe with a long-named ingredient (e.g.,
  "Freshly ground black peppercorns") and a mix of short-named ones.

## Smoke 1 — Readable at arm's length (~1 min)
1. Open a recipe with ≥ 6 ingredients. Tap "Start Cooking".
2. Verify each chip shows: quantity + unit on top (e.g. "3 cloves") in
   the accent color (warm orange in light, muted in dark), name below
   in regular text weight.
3. Text size is noticeably larger than pre-cmlp-3 (14px vs 13px).
4. Chips hug short-named ingredients tightly (no "empty padding").
5. Long-named ingredients ("Freshly ground black peppercorns") wrap to
   2 lines and show ellipsis if longer.

## Smoke 2 — Dynamic Type scaling (~1 min)
1. iOS: Settings → Accessibility → Display & Text Size → Larger Text →
   push to second-to-largest setting.
2. Reopen the recipe + Cook mode.
3. Chips still render legibly. Long names wrap; no chip content
   clipped. No `RenderFlex overflowed` yellow-striped warnings visible.

## Smoke 3 — Checked state (~30s)
1. Tap an ingredient chip in cook mode.
2. Chip flips to the `cookCompleted` background; both quantity + name
   show strikethrough; check icon appears on the left.
3. Tap again — chip returns to unchecked state.

## Smoke 4 — Light + dark + system themes (~1 min)
1. Toggle the app theme between light / dark / system.
2. In each theme, verify chip typography (the name at 14px w500, the
   quantity at 14px w600 in the accent color) is readable.

## Automated coverage
- `flutter test test/cook_mode_test.dart` — pass, including new
  typography + IntrinsicWidth + TextScaler(2.0) tests.
- `flutter test test/cook_mode_resume_test.dart` — pass (restored
  strict `find.text('Ingredient 1')` tap).
- `flutter test test/meal_cook_mode_test.dart test/meal_cook_mode_ingredients_test.dart test/cook_mode_gesture_test.dart test/cook_mode_timer_test.dart`
  — all pass.

## Sign-off
Story ships when the four smokes above show no regression and the
automated suites are green.
