# QA Walkthrough — mcal-9 (Flutter: Meal detail action-bar wiring + recurring plans)

## Pre-reqs
- A Meal with at least 2 component recipes (Kale Salad Meal seed works).
- At least one shopping list present on the account.

## Plan-for-Date from Meal detail
1. Open Meal detail. Action bar shows Favorite · Plan · Shop · Share · Archive · Edit. All six enabled.
2. Tap **Plan**. The plan-meal sheet opens.
3. Verify:
   - Segmented button at top is **Meal** (pre-selected).
   - `MealAutocompleteField` shows a "Linked to <MealName>" chip pre-filled.
   - User only has to pick date / meal-type / repeats.
4. Pick "Tomorrow, Dinner". Save. Snackbar reads "Kale Salad Meal added to calendar".
5. Switch to the Calendar tab and confirm the event is rendered with Icons.layers + "2 recipes" caption.

## Add-to-Shopping-List from Meal detail (single-list user)
1. Open Meal detail. Tap **Shop**.
2. First-time path: the default shopping list is picked automatically; snackbar reads "Added N items from <MealName>".
3. Second tap in the same session: adds again (idempotency handled server-side via dedupe).

## Add-to-Shopping-List from Meal detail (multi-list user)
1. Open Meal detail on an account with 2+ shopping lists.
2. Tap **Shop**. A list-picker sheet appears.
3. Pick a list. Snackbar fires; that list is remembered as the default going forward.

## Partial-unavailability
1. Archive one of the Meal's component recipes.
2. Tap **Shop**. Snackbar reads "Added N items (some components unavailable)".

## Recurring plans screen
1. From Profile → Recurring Plans, confirm:
   - Recipe rules render the recipe title (or free-text title) as today.
   - Meal rules render the Meal name as title + "(2 recipes)" suffix.
   - The summary line below still reads "Every Monday · Dinner" etc.
2. Tapping a Meal rule opens the existing Delete-series edit sheet (tap-to-edit-into-plan-meal-sheet is deliberately out-of-scope for this epic — would require recurrence-rule edit surface in plan-meal sheet).

## Pass criteria
- Plan / Shop actions both launch their expected flows on every account shape.
- Snackbar wording reflects the specific meal name and partial-unavailability states.
- Recurring Plans row renders Meal rules with correct "(N recipes)" suffix.

## Tests
- `app/test/features/meals/meal_detail_screen_test.dart` — existing Plan/Shop-disabled assertion replaced with enablement + onTap-non-null checks.
- `app/test/features/profile/recurring_plans_screen_test.dart` — +1 Meal-rule rendering test.
- Full calendar + meals + profile suite: 202 pass locally.
