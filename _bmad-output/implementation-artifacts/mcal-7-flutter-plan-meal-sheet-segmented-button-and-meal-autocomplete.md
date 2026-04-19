# Story mcal-7 — Flutter: plan-meal sheet Recipe/Meal SegmentedButton + MealAutocompleteField

**Status:** done
**Epic:** epic-meals-calendar
**Depends on:** mcal-3 (backend accepts meal_id XOR recipe_id), mcal-5 (GET /v1/meals?q= autocomplete endpoint).

## Scope

1. Promote `kMealComponentCountLabel(int n) => '$n recipes'` helper from `meal_tile.dart` (also consumed by calendar surfaces in mcal-8).
2. Extend `MealEvent` + `RecurrenceRule` models with `mealId` + `mealSummary`.
3. Extend `MealCalendarService.createMealEvent` / `updateMealEvent` / `createRecurrenceRule` / `updateRecurrenceRule` with `mealId` (XOR with `recipeId` — debug assert).
4. Extend `MealService` with `searchMeals(query, {limit})` and `addToShoppingList(mealId, shoppingListId)`.
5. Extend `ApiClient.listMeals` with an optional `q` param. Add `addMealToShoppingList(mealId, data)`.
6. New `MealAutocompleteField` widget mirroring `RecipeAutocompleteField` (300ms debounce, calls `GET /v1/meals?q=`).
7. `PlanMealSheet`: add `SegmentedButton<PlanMealType>` above picker row, wrap body in `SingleChildScrollView`, new `initialPlanMealType` / `initialMealId` / `initialMealName` props, `_save()` XOR branching.
8. Widget tests for plan-meal Meal mode + autocomplete field.

## File List

- `app/lib/features/meals/widgets/meal_tile.dart` [MODIFY] — export `kMealComponentCountLabel`.
- `app/lib/features/calendar/models/meal_event.dart` [MODIFY] — add `MealSummary`, `MealEvent.mealId`, `MealEvent.mealSummary`, `RecurrenceRule.mealId`, `RecurrenceRule.mealSummary`.
- `app/lib/features/calendar/services/meal_calendar_service.dart` [MODIFY] — `mealId` params + XOR assertions.
- `app/lib/features/meals/services/meal_service.dart` [MODIFY] — add `searchMeals`, `addToShoppingList`.
- `app/lib/core/services/api_client.dart` [MODIFY] — `listMeals(q:)` + `addMealToShoppingList`.
- `app/lib/features/calendar/widgets/meal_autocomplete_field.dart` [NEW]
- `app/lib/features/calendar/widgets/plan_meal_sheet.dart` [MODIFY] — SegmentedButton, MealAutocompleteField swap, SingleChildScrollView, new props.
- `app/test/features/calendar/plan_meal_sheet_test.dart` [MODIFY] — Meal mode coverage.
- `app/test/features/calendar/meal_autocomplete_field_test.dart` [NEW]

## Acceptance Criteria

- SegmentedButton renders Recipe/Meal at top of picker row; default Recipe unless `initialPlanMealType: PlanMealType.meal`.
- Body wrapped in `SingleChildScrollView` — small-screen fit.
- Toggle swaps between `RecipeAutocompleteField` and `MealAutocompleteField` — picked recipe/meal is cleared when switching.
- `_save()` dispatches `createMealEvent`/`createRecurrenceRule` with `mealId` XOR `recipeId`.
- Debug `assert` catches misuse at the service layer before network.
- `MealAutocompleteField` — 300ms debounce, 2s timeout, "N recipes" badge on results.
- Widget tests pass.
- `dart analyze lib/features/calendar/` + `dart analyze lib/features/meals/` clean.
- `flutter test test/features/calendar/` + `flutter test test/features/meals/` green.
