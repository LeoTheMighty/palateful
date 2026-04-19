# QA Walkthrough — mcal-3

Backend-only story. No UI surface until mcal-7/mcal-8/mcal-9 land. QA is limited to API contract verification; clients consuming the new response keys will be added in the Flutter stories.

## Checklist

- [x] `POST /v1/meal-events` with both `recipe_id` and `meal_id` → 422 code 135.
- [x] `POST /v1/meal-events` with `meal_id` only → 201, response includes `meal_id` + `meal_summary`.
- [x] `POST /v1/meal-events` with invalid `meal_id` → 404 code 300.
- [x] `POST /v1/meal-events` with archived Meal → 404 code 300.
- [x] `POST /v1/meal-events` when user lacks read on Meal's book → 403 code 301.
- [x] `PUT /v1/meal-events/{id}` mode switch: recipe_id event → meal_id clears recipe.
- [x] `PUT /v1/meal-events/{id}` mode switch: meal_id event → recipe_id clears meal.
- [x] `PUT /v1/meal-events/{id}` with both ids → 422 code 135.
- [x] `GET /v1/meal-events/{id}` returns `meal_summary` when event is Meal-linked.
- [x] `GET /v1/meal-events` list hydrates `meal_summary` for mixed recipe+meal events.
- [x] Recipe-only paths byte-identical to pre-epic: `meal_id: null, meal_summary: null` added (additive).
- [x] `POST /v1/recurrence-rules` symmetric behavior (XOR, access, 404, meal_summary hydration).
- [x] `PUT /v1/recurrence-rules/{id}` scope=all: mode switch Recipe↔Meal.
- [x] `PUT /v1/recurrence-rules/{id}` scope=this_and_following: new rule inherits meal_id.
- [x] `GET /v1/recurrence-rules/{id}` + list: meal_summary populated when `meal_id` set.
- [x] 2002 API tests pass at 100% coverage.
- [x] `npx nx run api:lint` clean.

## What's next

- mcal-5: `GET /v1/meals?q=&limit=8` autocomplete and `POST /v1/meals/{id}/add-to-shopping-list` + `POST /v1/meal-events/{id}/add-to-shopping-list` endpoints — the transport that plumbs `aggregate_meal_ingredients` from mcal-2 into real HTTP.
- mcal-6: materializer `_resolve_title` gains a `rule.meal_id` branch so Meal-rule occurrences render with the Meal's name instead of the fallback "Meal" string.

Materializer still falls back to `rule.title or "Meal"` for Meal rules; mcal-6 fixes this. That means right now, if a Flutter client (when it lands) creates a Meal rule and the materializer runs before mcal-6, the rendered event title will be the fallback string. This is OK because Flutter stories haven't shipped yet.
