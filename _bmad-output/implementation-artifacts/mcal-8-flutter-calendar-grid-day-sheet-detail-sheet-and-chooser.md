# Story mcal-8 — Flutter: calendar grid + day sheet + detail sheet + chooser

**Status:** done
**Epic:** epic-meals-calendar
**Depends on:** mcal-7 (MealEvent model has mealId/mealSummary), mcal-3 (backend hydrates meal_summary), mcal-5 (per-event add-to-shopping-list endpoint).

## Scope

1. `calendar_screen.dart` `_buildEventTile` renders Meal events with `Icons.layers` badge + "N recipes" caption under the meal-type chip. Thumbnail uses first component image URL (collage-first); falls back to layers icon. Recipe events render unchanged (regression).
2. `calendar_screen.dart` `_addIngredientsFromEvent` routes Meal events through the new `POST /v1/meal-events/{id}/add-to-shopping-list` endpoint; Recipe events still call `populateFromRecipe` for zero-regression.
3. Per-card shopping-cart icon is visible for Meal events too.
4. `day_detail_sheet.dart` `_DayMealRow` mirrors the tile rendering branch.
5. `meal_detail_sheet.dart` gains an "Open Meal" outlined button when `event.mealId != null` (pushes `/meals/:id`); "Open Recipe" action now fetches the Meal and opens the `CalendarRecipeChooserSheet` when 2+ components are available, or pushes directly when exactly 1.
6. NEW `calendar_recipe_chooser_sheet.dart` — "Which recipe?" bottom sheet listing available components (omits unavailable entirely).

## File List

- `app/lib/features/calendar/calendar_screen.dart` [MODIFY] — tile branching, per-card cart icon visibility, routing.
- `app/lib/features/calendar/widgets/day_detail_sheet.dart` [MODIFY] — meal-event row rendering.
- `app/lib/features/calendar/widgets/meal_detail_sheet.dart` [MODIFY] — Open Meal row + chooser integration.
- `app/lib/features/calendar/widgets/calendar_recipe_chooser_sheet.dart` [NEW]
- `app/test/features/calendar/meal_detail_sheet_test.dart` [MODIFY] — 3 new Meal-event tests.
- `app/test/features/calendar/calendar_recipe_chooser_sheet_test.dart` [NEW]

## Acceptance Criteria

- Meal events render with `Icons.layers` inline badge + "2 recipes" caption (via `kMealComponentCountLabel`).
- Recipe events render byte-identical to today (regression fixtures pass).
- "Open Meal" row is visible iff `event.mealId` is set; pushes `/meals/:id`.
- "Open Recipe" on a Meal event fetches the Meal and shows chooser when 2+ components; single-component case pushes directly.
- Chooser title "Which recipe?"; omits unavailable components; tap pushes `/recipes/:id` and pops the sheet.
- Per-card shopping-cart icon is live for Meal events and routes through the new per-event endpoint.
- Full calendar + meals widget suite green.
