# cmm-5 — QA walkthrough

This story wires component-aware timer label disambiguation in meal
cook mode. cmm-6 ships the post-cook sheet; cmm-7 ships the Resume
gate (with the "while you were away" snackbar).

## Setup
- Build the app from `main`.
- Need a 2+ component meal.

## Smoke 1 — Cross-component disambiguation (~2 min)
1. Open meal detail → tap Start Cooking.
2. Tap the manual-timer icon → enter "5 minutes" + label "simmer" → Start.
3. Active-timers row at top now shows a "simmer" chip.
4. Advance into the second component's step range.
5. Tap manual-timer again → enter "3 minutes" + label "simmer" → Start.
6. Active-timers row now has TWO chips: "simmer" (first) and
   "<Component> · simmer" (second). The first never gets renamed.

## Smoke 2 — Empty-label default (~1 min)
1. Tap manual-timer → leave the label field empty (or keep "Timer").
2. Enter minutes → Start.
3. New chip should appear with the current component's name as its label.
4. Repeat in the SAME component → second chip is "<Component> 2".

## Smoke 3 — Notification body (best-effort, requires real device)
1. Start a "simmer" timer in the first component, then a second
   "simmer" in a different component.
2. Background the app and let both fire.
3. The OS notifications should read "simmer timer is done" and
   "<Component> · simmer timer is done" respectively.

## Smoke 4 — Recipe cook regression (~1 min)
1. Open a single-recipe cook (NOT meal cook).
2. Start two manual timers with the same label (e.g. "bake").
3. They should disambiguate via the LEGACY " 2" suffix path —
   "bake" and "bake 2" — NOT with a component prefix.

## Negative
- No multi-row post-cook sheet (cmm-6).
- No Resume gate or "while you were away" snackbar (cmm-7).

## Automated coverage
- `flutter test test/meal_cook_mode_timers_test.dart` — 3 tests
  covering cross-component disambiguation, empty-label default, and
  same-component " 2" suffix fallthrough.

## Sign-off
Story is shippable when smokes 1, 2, 4 pass and the automated suite
is green.
