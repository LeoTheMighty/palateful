# cmm-7 — QA walkthrough (final story)

This story closes out epic-cook-mode-meal: persistent resume + drift
handling for meal cook. End-to-end walkthrough covers the whole epic.

## Setup
- Build the app from `main`. No new env vars.
- Need a 3-component meal with at least 7+, 4+, 9+ steps.

## Smoke 1 — Resume after kill (~5 min)
1. Open meal detail → Start Cooking.
2. Advance to Salad's step 2. Check off 5 ingredients across the strip.
3. Start a 5-minute manual timer labelled "simmer".
4. Force-quit the app.
5. Re-open → tap the meal → tap Start Cooking.
6. Resume gate sheet appears with copy "<MealName>" + "Salad · step
   2 of 4 · started <relative> · 5 ingredients checked · 1 timer".
7. Tap Resume → cook UI mounts at Salad · step 2; ingredients still
   checked; timer chip restored with correct remaining time.

## Smoke 2 — Start Over (~1 min)
1. From the Resume gate (after kill), tap Start Over.
2. Cook UI mounts at Dressing · step 1. No ingredients checked.

## Smoke 3 — Meal-version drift (~3 min)
**Hard to reproduce naturally** — needs editing the meal between
sessions. The automated test
`meal-version drift: clamps current_step + drift snackbar` covers the
clamp + snackbar.

Manual reproduction (if you have access to the SharedPreferences
inspector or can edit `cook_session_meal_<id>` JSON):
1. Save a snapshot with `current_step: 99`.
2. Re-open. Resume → cook UI mounts at the last flat-step + snackbar
   "Meal changed since your last session — picking up at the last step".

## Smoke 4 — Stable-key drift (~3 min)
Manual reproduction:
1. Cook a meal, check off some ingredients, kill the app.
2. Edit one of the component recipes to remove ingredients.
3. Re-open meal cook → Resume → snackbar "Ingredients changed since
   your last session" appears, and the orphan checks are silently
   dropped (only valid keys re-checked).

## Smoke 5 — Expired-timer "while you were away" (~3 min)
1. Start a 1-minute timer in cook mode.
2. Force-quit. Wait 90+ seconds.
3. Re-open meal → Start Cooking → Resume.
4. Snackbar appears: "While you were away: <ComponentName> · simmer
   timer finished" (or similar).

## Smoke 6 — Reset / Finish cooking now still clear session (~2 min)
1. Cook a meal partially. Tap overflow → Reset cook → confirm.
2. Force-quit, re-open. No Resume gate (session was cleared).
3. Cook again partially. Tap overflow → Finish cooking now → confirm.
4. Submit ratings.
5. Force-quit, re-open. No Resume gate (Finish cleared the session
   on submission).

## End-to-end smoke (covers cmm-1..cmm-7) (~10 min)
1. From meal detail, tap Start Cooking FAB.
2. Verify section header "Dressing · 1 / 7" above the step card.
3. Verify combined ingredient strip shows source-tag chips.
4. Start a "simmer" timer on Dressing → advance to Salad → start
   another "simmer" → second chip is "Salad · simmer".
5. Advance to Grilled Chicken's range → cook through.
6. Tap Done on the final flat-step → multi-row post-cook sheet opens.
7. Rate components 5/4/0 → tap Done → 2 POSTs fire, sheet closes,
   meal detail refreshes with the new cook logs.
8. Open the meal again → no Resume gate (session was cleared).

## Negative
- All recipe-cook flows continue to work unchanged (single-row
  post-cook sheet, no section header, no source tags, legacy " 2"
  timer disambiguation).

## Automated coverage
- `flutter test test/meal_cook_mode_resume_test.dart` — 6 tests.
- Full app suite — 1249 / 1249 passing.
- Per-story suites:
  - cmm-1: `test/cook_plan_test.dart` (13)
  - cmm-1: `test/cook_mode_test.dart` (11) — recipe cook regression
  - cmm-2: `test/meal_cook_mode_test.dart` (7)
  - cmm-2: `test/features/meals/meal_detail_screen_test.dart` (4 new)
  - cmm-3: `test/meal_cook_mode_sectioning_test.dart` (3)
  - cmm-4: `test/meal_cook_mode_ingredients_test.dart` (9)
  - cmm-5: `test/meal_cook_mode_timers_test.dart` (3)
  - cmm-6: `test/meal_post_cook_feedback_test.dart` (6)
  - cmm-6: `test/post_cook_feedback_test.dart` (9) — single-recipe regression
  - cmm-7: `test/meal_cook_mode_resume_test.dart` (6)

## Sign-off
Epic shippable when smokes 1, 2, 5, 6 + the end-to-end pass and the
automated suite is green on the device. Smokes 3 and 4 are nice-to-
have manual confirmations of behaviour the automated suite already
verifies.
