# QA Walkthrough — mcal-5

Backend-only. UI surfaces come with mcal-7 / mcal-9 (Flutter).

## Checklist

- [x] `GET /v1/meals?q=Kale&limit=8` returns matching Meals scoped to readable books.
- [x] `GET /v1/meals?q=%20` (whitespace only) returns the same list as `GET /v1/meals` with no text filter.
- [x] `GET /v1/meals?limit=10000` silently caps at 50.
- [x] `POST /v1/meals/{id}/add-to-shopping-list` returns a summed per-ingredient list (same-unit merge verified).
- [x] Re-posting the same (meal_id, shopping_list_id) is a no-op — `items_skipped` counts the duplicates.
- [x] Archived Meal → 404.
- [x] Non-reader of Meal's book → 403.
- [x] Missing shopping list → 404.
- [x] Non-writer of shopping list → 403.
- [x] `POST /v1/meal-events/{id}/add-to-shopping-list` on a recipe event: expands via `recipe.ingredients`; items carry `recipe_id` + `meal_event_id`, `source_meal_id=null`.
- [x] Same endpoint on a Meal event: expands via `aggregate_meal_ingredients` (sum-within-meal); items carry `meal_event_id` + `source_meal_id`, `recipe_id=null`.
- [x] Free-text event → 422.
- [x] Event whose linked recipe was hard-deleted (orphan relationship) → 404.
- [x] Archived / orphan-ingredient RecipeIngredient rows are skipped without crashing.
- [x] `npx nx run api:lint` clean.
- [x] 2021 API tests pass at 100% coverage.

## What's next

- mcal-6: wire `meal_id` into materializer (`_resolve_title` + `insert_values`) so Meal-rule occurrences pick up the Meal's name. Also adds the missing `POST /v1/cooking-logs` handler with Meal fan-out (one parent + N children).
- mcal-7, 8, 9: Flutter surfaces (plan-meal sheet segmented button + MealAutocompleteField, calendar rendering + chooser, Meal-detail Plan-for-Date / Add-to-Shopping-List wiring).

## Follow-up

When mcal-6 rewrites `_resolve_title` in the materializer, Meal-rule materialized events will pick up the Meal's name. Until then, they surface as `rule.title or "Meal"` — a harmless fallback because no Flutter client surfaces Meal rules yet.
