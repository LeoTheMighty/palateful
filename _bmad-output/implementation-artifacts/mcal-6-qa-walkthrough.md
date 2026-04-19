# QA Walkthrough — mcal-6

Backend-only. Flutter wiring lands in mcal-7/8/9.

## Checklist

- [x] Materializer `_resolve_title` returns `meal.name` for Meal-linked rules.
- [x] Falls back to `recipe.name` when only `recipe_id` is set (regression).
- [x] Falls back to `rule.title or "Meal"` when both lookups miss.
- [x] When both `meal_id` and `recipe_id` are unexpectedly set, Meal wins.
- [x] `insert_values` propagates `meal_id` and `calendar_id` so materialized Meal-rule events satisfy the XOR + NOT NULL constraints.
- [x] `POST /v1/cooking-logs` with `meal_event_id` (recipe event) → 1 row with `recipe_id` set, no children.
- [x] Same with a Meal event → 1 parent row + N children (one per live component); `parent_meal_log_id` chain intact.
- [x] Archived component recipe → skipped from fan-out; parent still writes.
- [x] Component with null `recipe` relationship → skipped; doesn't crash.
- [x] Direct `recipe_id` (no event) → 1 row.
- [x] Both `meal_event_id` and `recipe_id` → 422.
- [x] Neither set → 422.
- [x] Free-text event (`recipe_id=NULL, meal_id=NULL`) → 422.
- [x] Missing event / recipe → 404.
- [x] 2032 api tests + 259 utils tests pass at 100% coverage.

## What's next

Flutter stories:
- **mcal-7** — `plan_meal_sheet.dart` SegmentedButton Recipe|Meal + `MealAutocompleteField` widget; XOR-aware `_save()`; `initialPlanMealType` / `initialMealId` / `initialMealName` props.
- **mcal-8** — Calendar tile + day sheet + meal_event_detail_sheet render `meal_id` events with `Icons.layers` + "N recipes" caption; `CalendarRecipeChooserSheet` for "Which recipe?" disambiguation.
- **mcal-9** — Meal detail action-bar wiring (Plan-for-Date, Add-to-Shopping-List), `recurring_plans_screen.dart` Meal-rule rendering.

## Follow-up

The materializer's `insert_values` change to add `calendar_id` fixes a pre-existing NOT-NULL gap that was masked by tests. Worth a focused regression check during the next end-to-end run: the cron `advance_recurrence_windows` task that runs the materializer in production should be observed for 1-2 cycles to confirm no rule-update flow trips on the new column.
