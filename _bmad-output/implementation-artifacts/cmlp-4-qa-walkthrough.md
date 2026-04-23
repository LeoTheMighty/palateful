# cmlp-4 — QA walkthrough

## Setup
- Build app from the current `main`. No env vars.
- Sign in; create or open a meal with **2+ components** (ideally 3 —
  Dressing, Salad, Grilled Chicken). Each component should have at
  least 1–2 ingredients.

## Smoke 1 — Group headers replace dashed dividers (~1 min)
1. Open the meal. Tap "Start Cooking".
2. Scroll to the ingredient strip.
3. Verify each component name (e.g. `Dressing`) appears as a
   **typographic group header**: standalone text, slightly faded,
   with a thin horizontal rule below it. Then the chips for that
   component.
4. There should be **no** `--- From Dressing ---` dashed dividers
   anywhere.
5. Repeat across all 3 components.

## Smoke 2 — Section header above step card is gone (~30s)
1. Still in meal cook mode, look above the step card.
2. The old `Dressing · 1 / 7` section header banner is **gone**.
3. The step card sits directly below the progress bar.

## Smoke 3 — Accessibility (VoiceOver / TalkBack) (~1 min)
1. Enable VoiceOver (iOS) or TalkBack (Android).
2. Focus on a group header in the ingredient strip.
3. Hear it announced as "Dressing, heading" (or equivalent) before
   moving to the chips.

## Smoke 4 — 1-component meal: no group header (~30s)
1. Open a 1-component meal (or a recipe opened via single-recipe cook
   mode).
2. No group header text should appear — the ingredient list renders as
   a flat `Wrap` of chips (recipe-cook contract).

## Smoke 5 — Null-tag fallback: "Other" group (~30s, optional — hard
   to trigger in real data)
- Rare; only appears when a failed-load component's name is not yet
  known. If reproducible, confirm untagged ingredients appear under
  a group header labelled `Other` with its own divider.

## Automated coverage
- `flutter test test/meal_cook_mode_ingredients_test.dart` — pass
  (3 new cmlp-4 tests: group-header text, Semantics header flag,
  Other-group rendering).
- `flutter test test/meal_cook_mode_sectioning_test.dart` — pass
  (cmm-3 RecipeSectionHeader test deleted; boundary + progress-bar
  tests preserved).
- `flutter test test/cook_mode_test.dart test/meal_cook_mode_test.dart
  test/cook_mode_gesture_test.dart test/cook_mode_resume_test.dart
  test/cook_mode_timer_test.dart` — all pass.

## Sign-off
Story ships when the smokes above show no regression and the
automated suites are green. The `recipe_section_header.dart` file
remains on disk — it will be deleted in the multi-recipe-flow epic.
