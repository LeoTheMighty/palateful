# Story cmm-5 — Meal-level timers + component-name label disambiguation

**Status:** done
**Epic:** epic-cook-mode-meal
**Branch:** main

## Goal

Make meal-cook timers feel coherent across component boundaries: they
persist in the same row regardless of where the user is in the cook,
and labels self-disambiguate when two components both want a "simmer"
or "bake" timer. First-come-first-served: the second timer with a
duplicate label gets the `<ComponentName> · ` prefix; the first stays
verbatim. Manual-timer sheets default an empty label to the current
component name. Same-component empty-label collisions fall through to
the legacy ` 2` / ` 3` suffix from `epic-cook-mode-timers`.

## Acceptance Criteria — status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Active-timers row mounted at top, persists across boundaries | ✅ Done in cmm-2 (shared `ActiveTimersRow`) |
| AC2 | Label disambiguation: new collision → `<Component> · <label>`, existing label unchanged | ✅ Done — `_disambiguateMealTimerLabel` |
| AC3 | Manual-timer sheet empty/`Timer` default → current component name; same-component collision → ` 2` suffix | ✅ Done — see `_showManualTimerSheet` |
| AC4 | OS notification body + completion snackbar include the component name | ✅ Done — `_startTimer` schedules notif with the disambiguated label, which carries the prefix |
| AC5 | Widget tests: cross-component "simmer" disambiguation; manual empty defaults to component name; same-component fall-through to " 2" suffix | ✅ Done — 3 tests in `meal_cook_mode_timers_test.dart` |
| AC6 | Mock notification service: scheduled body includes component name | ✅ Done — `notif.scheduled.last['label'] == 'Salad · simmer'` |
| AC7 | Recipe cook (1-component) — no component-name prefixing; legacy " 2" path preserved | ✅ Done — `_disambiguateMealTimerLabel` returns requested unchanged when component name is null/empty (recipe cook screen path is unchanged in this story) |
| AC8 | "While you were away" snackbar with component-name prefix on Resume | ⏭ Deferred to cmm-7 — Resume flow ships there |

## File List

### New
- `app/test/meal_cook_mode_timers_test.dart` (3 widget tests)

### Modified
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
  - `_startTimer` runs every label through `_disambiguateMealTimerLabel`
  - `_showManualTimerSheet` defaults empty / `Timer` to current
    component name; non-empty user labels go straight to `_startTimer`
  - New `_disambiguateMealTimerLabel(requested, currentComponentName)`
    helper — adds `<Component> · ` prefix on collision; chains
    additional ` 2`/` 3` suffixes if the prefixed form ALSO collides
    (defensive, rarely hit)

## Implementation notes

- Notification body and Live Activity label both pick up the
  disambiguated `displayLabel`. The original `label` parameter into
  `_startTimer` is treated as the "intent" label; the chip / notif
  / live activity all see the rewritten one.
- Recipe cook is unchanged — `cook_mode_screen.dart` doesn't import
  `_disambiguateMealTimerLabel`; the legacy `disambiguateTimerLabel`
  (`" 2"` suffix) handles all collisions there.
- AC8's "while you were away" snackbar is part of the Resume flow,
  which is wholesale wired in cmm-7. The component-name prefix
  contract is already enforced in `_disambiguateMealTimerLabel`, so
  cmm-7 just needs to surface the snackbar copy from the same
  prefixed labels.

## QA checklist

See `cmm-5-qa-walkthrough.md`.

## Verification

- `flutter test test/meal_cook_mode_timers_test.dart` — 3 tests.
- `flutter test test/meal_cook_mode_test.dart test/meal_cook_mode_sectioning_test.dart test/meal_cook_mode_ingredients_test.dart test/meal_cook_mode_timers_test.dart test/cook_plan_test.dart test/cook_mode_test.dart` — 46 green.
- `dart analyze lib/features/recipes/cook_mode/meal/` — no issues.
