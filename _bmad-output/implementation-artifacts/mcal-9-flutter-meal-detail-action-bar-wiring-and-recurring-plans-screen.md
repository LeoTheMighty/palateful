# Story mcal-9 — Flutter: Meal detail action-bar wiring + recurring plans screen

**Status:** done
**Epic:** epic-meals-calendar
**Depends on:** mcal-7 (PlanMealSheet supports Meal mode), mcal-5 (POST /v1/meals/{id}/add-to-shopping-list).

## Scope

1. `meal_detail_screen.dart` `_ActionBar`:
   - Drop disabled tooltips on Plan + Shop slots.
   - Wire Plan-for-Date: opens `PlanMealSheet` with `initialPlanMealType: PlanMealType.meal`, `initialMealId`, `initialMealName`.
   - Wire Add-to-Shopping-List: picks default list (or opens picker for multi-list users) and calls `MealService.addToShoppingList(mealId, shoppingListId)`. Surfaces "Added N items from <MealName>" (or partial-unavailability variant) snackbar.
2. `rule_row.dart` renders Meal rules with meal name as title + "(N recipes)" suffix. Falls back cleanly to "Meal plan" when `mealSummary` is absent.

## File List

- `app/lib/features/meals/meal_detail_screen.dart` [MODIFY]
- `app/lib/features/profile/recurring_plans/widgets/rule_row.dart` [MODIFY]
- `app/test/features/meals/meal_detail_screen_test.dart` [MODIFY]
- `app/test/features/profile/recurring_plans_screen_test.dart` [MODIFY]

## Acceptance Criteria

- Plan + Shop labels render; both are enabled (no tooltip).
- Tapping Plan opens the plan-meal sheet with the Meal pre-filled in Meal mode.
- Tapping Shop picks the default shopping list (or opens picker) and posts to `/v1/meals/{id}/add-to-shopping-list`. Snackbar communicates items added.
- Partial-unavailability response surfaces the "(some components unavailable)" copy.
- Recurring Plans screen renders Meal rules as "Kale Salad Meal (2 recipes)" with the "Every Monday · Dinner" summary unchanged.
- Full calendar + meals + profile widget suite green.
