# cmm-3 — QA walkthrough

This story adds the section header above the step card and the
component boundary rules + Semantics on the StepNavigator. cmm-4
adds source-tagged ingredients; cmm-5 adds component-aware timers;
cmm-6 adds the post-cook sheet; cmm-7 adds resume.

## Setup
- Build the app from `main`. No new env vars.
- Need a 3-component meal (e.g. Dressing + Salad + Grilled Chicken)
  with at least 7+, 4+, 9+ steps respectively.

## Smoke 1 — Section header transitions (~3 min)
1. Open meal detail → tap Start Cooking → cook UI mounts.
2. Above the step card: header reads "Dressing · 1 / 7" (component
   name + step number / component step count).
3. Tap Next 7 times. Header transitions to "Salad · 1 / 4".
4. Tap Next 4 times. Header transitions to "Grilled Chicken · 1 / 9".
5. Tap Prev once. Header transitions to "Salad · 4 / 4".

## Smoke 2 — StepNavigator boundary separators (~1 min)
1. From the same meal, look at the step pills along the bottom.
2. There should be a small visible vertical rule between pill #7 and
   pill #8 (Dressing → Salad boundary), and another between pill #11
   and pill #12 (Salad → Grilled Chicken).
3. There is NO rule before pill #1 (the first pill).

## Smoke 3 — Flat progress bar (~1 min)
1. From the same 3-component meal (totalSteps = 20), advance to
   flat-step 10.
2. Progress bar should read approximately 50%. The bar is flat-total,
   not per-component — the section header is the per-component signal.

## Smoke 4 — Recipe cook (1-component) regression (~1 min)
1. Open any single-recipe cook flow (NOT a meal cook).
2. Verify there is NO section header above the step card (recipe-cook
   stays pixel-identical to cmm-2 / pre-meal behavior).
3. StepNavigator pills have NO vertical rule separators.

## Negative
- No source-tag chips on ingredients (cmm-4).
- No "Finish cooking now" overflow item (cmm-6).
- No Resume gate sheet (cmm-7).

## Automated coverage
- `flutter test test/meal_cook_mode_sectioning_test.dart` — 3 tests
  (section-header transitions, boundary keys, flat progress).
- `flutter test test/meal_cook_mode_test.dart` — 7 tests (load,
  partial-load, retry, offline, banner-retry).
- `flutter test test/cook_mode_test.dart` — recipe-cook unchanged.

## Sign-off
Story is shippable when smokes 1, 2, 4 show no regression and the
automated suite is green.
