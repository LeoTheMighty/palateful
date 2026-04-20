# QA Walkthrough — cmt-6 Cook Mode Timers end-to-end

Sweep covers the three timer sources (extracted, regex, manual) plus the hybrid-as-fallback rule, on a real device + the widget suite.

## Automated checklist

- [x] `flutter test` passes for all cook_mode_* files (96 tests: cook_mode_test, cook_mode_gesture_test, cook_mode_timer_test, offline_cook_mode_test, post_cook_feedback_test, timer_regex_test, step_timers_row_test, manual_timer_sheet_test, cook_mode_timers_integration_test).
- [x] `npx nx run utils:test` / `npx nx run api:test` / eval suite all green.
- [x] `npx nx run utils:lint` / `npx nx run api:lint` / `dart analyze lib/features/recipes/cook_mode/` clean (only pre-existing warnings).

## Manual device QA (to be run on-device before release)

### Path A — recipe imported post-cmt-2 with extracted timers
1. Import a fresh URL recipe with active durations (e.g. chicken_tikka_masala eval fixture source).
2. Open → tap "Cook" → advance to step 2.
3. Expect concise `OutlinedButton` like "3 min simmer" + tooltip "3–5 min in recipe" if original had a range.
4. Tap → active-timers row shows the chip → background the app.
5. OS notification fires at expiry → foreground → snackbar says "Timer done: simmer".

### Path B — legacy recipe, no extracted timers, regex fallback
1. Open a recipe imported before this epic (or one where `step.timers` is empty).
2. Find a step like "Bake 25 minutes, rotate at 12 minutes, broil last 2 minutes".
3. Expect 3 `OutlinedButton`s in a horizontally scrollable row — no cap truncation, overflow scrolls.
4. Tap one → timer starts as in Path A.

### Path C — no extracted + no regex match → manual
1. Open a recipe whose step reads "Let the dough rise until doubled" (no duration mentioned).
2. Expect 0 inline buttons under the step.
3. Tap the `Icons.timer_outlined` header button (48×48 tap target).
4. Bottom sheet opens → type 45 → label "rise" → Start → active-timers row shows a "rise" chip.
5. Tap the header icon again → accept default "Timer" → Start → chip shows "Timer" (first) + later adding another "Timer" shows "Timer 2".

### Hybrid-as-fallback verification
1. Open a recipe with `step.timers:[{simmer, 3}]` AND instruction text like "Simmer 3 min then bake 25 min".
2. Expect exactly ONE button ("3 min simmer"). The regex MUST NOT fire to add a 25-min button when structured is non-empty.

### Offline behaviour
1. Toggle airplane mode after opening cook-mode.
2. Header offline indicator shows; AI chat button hidden; **timer icon button remains visible and tappable**.
3. Open sheet → 15 → Start → timer starts normally.

## Regression

- [x] Epic 6 ACs preserved — `cook_mode_test`/`cook_mode_gesture_test`/`cook_mode_timer_test`/`offline_cook_mode_test`/`post_cook_feedback_test` all green.
- [x] Step text renders at 24px, swipe gestures work, offline indicator persists, post-cook feedback sheet opens as before.

## What's next

- Once the `epic-cook-mode-polish` CookModeTheme extension lands, the timer accent will pick up `cookTimer` token automatically via `resolveCookTimer` (no app change needed).
- Extraction baseline (first `timer_extraction_f1` post-merge eval run) to be recorded in `recipe_extraction_evaluator.py` — see the TODO note next to `_TIMER_DURATION_SLACK`.
