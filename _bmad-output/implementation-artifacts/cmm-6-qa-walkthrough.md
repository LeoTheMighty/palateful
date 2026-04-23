# cmm-6 — QA walkthrough

This story ships the multi-row post-cook sheet + early-finish overflow
item. cmm-7 wires the Resume gate (last remaining story).

## Setup
- Build the app from `main`.
- Need a 3-component meal with at least 2-3 steps per component.

## Smoke 1 — Happy-path full meal cook (~5 min)
1. Open meal detail → Start Cooking.
2. Walk through every step of every component.
3. On the final flat-step, the Next button changes to "Done".
4. Tap Done → multi-row post-cook sheet opens with one row per
   component (3 rows for a 3-component meal).
5. Each row shows the component name + 5-star rating row + optional
   notes field. The sheet is non-dismissible.
6. Rate component 1 → 5 stars; component 2 → 4 stars; leave
   component 3 at 0.
7. Tap Done → 2 POST /v1/cooking-logs requests fire to the backend
   for components 1 and 2.
8. Sheet closes; cook-mode screen pops back to meal detail.
9. Meal detail's `cooking_history_provider` should refetch and reflect
   the new cook logs.

## Smoke 2 — Early finish (~3 min)
1. Open meal detail → Start Cooking.
2. Cook component 1 fully (advance through every step). Then
   advance one or two steps into component 2.
3. Tap the overflow menu (top-right) → "Finish cooking now".
4. Confirmation sheet appears: "Finish this meal early?" with
   Cancel (left) / Finish (right, red).
5. Tap Cancel → cook UI intact, no state change.
6. Re-open overflow → Finish cooking now → tap Finish.
7. Multi-row sheet opens with **2 rows** (component 1 + 2; not 3 —
   component 3 was never entered).
8. Rate 5 / 4 → tap Done → 2 POSTs.

## Smoke 3 — Partial failure (best-effort)
- Hard to reproduce without backend cooperation. Code path: if any
  POST fails, a "Cooked X of Y components logged" snackbar appears
  but the sheet still closes and the persister clears.

## Smoke 4 — All-zeroes path (~1 min)
1. Cook a meal end-to-end → tap Done.
2. Leave every rating at 0 → tap Done.
3. Sheet closes with no API calls. Snackbar reads "Meal finished".

## Smoke 5 — Recipe cook regression (~1 min)
1. Open a single-recipe cook (NOT meal cook).
2. Tap Done → existing single-row post-cook sheet renders (5 stars,
   notes, Save, Skip). Pixel-identical to pre-meal cook.

## Negative
- No Resume gate sheet on entry (cmm-7).
- No "Ingredients changed" snackbar (cmm-7).

## Automated coverage
- `flutter test test/meal_post_cook_feedback_test.dart` — 6 tests
  covering the multi-row layout.
- `flutter test test/post_cook_feedback_test.dart` — 9 tests covering
  the single-row regression.

## Sign-off
Story is shippable when smokes 1, 2, 4, 5 pass and the automated
suite is green.
