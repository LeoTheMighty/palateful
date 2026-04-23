# cmlp-1 — QA walkthrough

## Setup
- Build app from the current `main`. No env vars.
- Sign in; need at least one recipe with steps, and one 2+ recipe meal.

## Smoke 1 — Recipe cook mode (~1 min)
1. Open any recipe with ≥ 2 steps. Tap "Start Cooking".
2. Verify header: back arrow · recipe name · timer · cooking-time badge ·
   overflow. **No `×` icon anywhere in the header.**
3. Tap the back arrow — exits cook mode to recipe detail.
4. Re-enter cook mode, tap the overflow (`⋮`). Menu still shows "Reset
   cook"; pick it and confirm the sheet works.
5. The overflow icon sits immediately right of the cooking-time badge —
   no gap big enough to look like a missing slot.

## Smoke 2 — Meal cook mode (~1 min)
1. Open a 2+ recipe meal, tap "Start Cooking".
2. Same header verification: no `×` icon.
3. Overflow still has both "Reset cook" and "Finish cooking now" — pick
   each to confirm the menu is wired.

## Smoke 3 — Edge-right padding (quick visual)
- Overflow icon doesn't touch the right edge of the screen; the
  `fromLTRB(8, 4, 12, 4)` padding leaves 12dp breathing room.

## Automated coverage
- `flutter test test/cook_mode_resume_test.dart` — all 15 tests pass,
  including the updated overflow-rightmost test.
- `flutter test test/cook_mode_test.dart test/meal_cook_mode_test.dart`
  — pass; no other test regressed.

## Sign-off
Story ships when the three smokes above show no regression and both
automated suites are green.
