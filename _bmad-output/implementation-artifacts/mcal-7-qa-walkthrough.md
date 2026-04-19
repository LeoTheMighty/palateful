# QA Walkthrough — mcal-7 (Flutter: plan-meal sheet Recipe/Meal SegmentedButton)

## Pre-reqs
- Dogfood account with at least 2 writable calendars and at least one Meal with 2 components (use the existing seeded Kale Salad Meal or create one via `/meals/create`).

## Happy path — quick-add Meal from calendar
1. Open the Calendar tab.
2. Tap the FAB or Tuesday's "+" button. Plan-meal sheet opens.
3. Verify a `SegmentedButton` with **Recipe** and **Meal** sits at the top of the picker row. Default: **Recipe**.
4. Tap the **Meal** segment. The recipe autocomplete swaps to the Meal autocomplete with hint "Search your meals".
5. Type "kale". After ~300ms, matching Meals render with a "2 recipes" caption.
6. Tap "Kale Salad Meal". A "Linked to Kale Salad Meal" chip appears below the field.
7. Tap Save. Expect no error. The sheet closes.

## Meal mode empty-state
- Toggle to Meal mode on a fresh sheet. Tap Save without picking. You should see a snackbar "Pick a meal to plan" and the button should be disabled until a Meal is picked.
- Type "zzzzz" into the Meal autocomplete — expect "No meals match "zzzzz"" and NO free-text fallback row.

## Mode-switch clears the other side
- Pick a Meal, then toggle to Recipe. The Linked chip should disappear.
- Pick a Recipe, then toggle to Meal. The Linked chip should disappear.

## Recipe mode (regression)
- Zero-meal user launches quick-add from FAB. Default is Recipe. Autocomplete = RecipeAutocompleteField.
- Save works with free-text OR with a picked recipe, as before.
- Recipe detail's "Plan for…" still opens with the recipe pinned; SegmentedButton is hidden (no mode-switch allowed post-pin).

## Small-screen fit
- On iPhone SE-class (568pt) simulator, open the sheet in Meal mode. The body should scroll; Save button should reachable via drag without clipping.

## Pass criteria
- Segmented toggle animates smoothly and swaps the picker widget without layout jump.
- Save dispatches with `meal_id` XOR `recipe_id` (never both) — inspect the request body in network inspector.
- Debug assert catches any accidental both-set at the service layer (caught by widget tests).

## Tests
- `app/test/features/calendar/plan_meal_sheet_test.dart` — 13 tests (Meal-mode group added this story).
- `app/test/features/calendar/meal_autocomplete_field_test.dart` — 3 tests (NEW).
- Full calendar + meals suite: 167 pass locally.
