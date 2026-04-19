# Story mcal-5 — Backend: Meal autocomplete + two add-to-shopping-list endpoints

**Status:** done
**Epic:** epic-meals-calendar
**Depends on:** mcal-2 (aggregate service), mcal-3 (meal_id on meal_event).

## Scope

Three HTTP surfaces. The Flutter stories (mcal-7, 9) will call them.

### 1. `GET /v1/meals?q=...&limit=...` — autocomplete extension

Extends the existing list endpoint (landed by md-3) with a `q` query param that does `name ILIKE '%q%' OR description ILIKE '%q%'`. Blank-after-strip inputs are treated as "no filter" to avoid a degenerate `%%` match. `limit` is clamped to 50 server-side so an autocomplete caller can't accidentally ask for a 10000-row page.

### 2. `POST /v1/meals/{meal_id}/add-to-shopping-list`

The "shop without scheduling" path. Expands a Meal into `shopping_list_items` via `aggregate_meal_ingredients` (mcal-2). Items get:

- `meal_event_id = NULL` (no calendar linkage)
- `source_meal_id = meal.id` (descriptive provenance)
- `recipe_id = NULL` (multi-recipe origin has no canonical single recipe)

Dedupe key within an already-populated list is `(ingredient_id, source_meal_id)` so re-tapping the same Meal on the same list is a no-op.

### 3. `POST /v1/meal-events/{event_id}/add-to-shopping-list`

Per-event path that replaces the now-deleted PopulateFromCalendar (cpms-2). Branches by event linkage:

- `recipe_id` set → expand via `recipe.ingredients` (parity with PopulateFromRecipe but keyed per-event).
- `meal_id` set → expand via `aggregate_meal_ingredients`.
- Neither set (free-text event) → 422.

Dedupe key is `(ingredient_id, meal_event_id)` so shopping the same event twice is a no-op; per-event separation preserves "Monday Meal" vs "Wednesday same Meal" as two independent groups.

## Error codes

No new error codes. Reuses existing `MEAL_NOT_FOUND`, `MEAL_ACCESS_DENIED`, `SHOPPING_LIST_NOT_FOUND`, `SHOPPING_LIST_ACCESS_DENIED`, `RECIPE_NOT_FOUND`, `MEAL_EVENT_NOT_FOUND`, `VALIDATION_ERROR`.

## File List

- `services/api/src/api/v1/meal/list_meals.py` [MODIFY] — `q` param + limit cap.
- `services/api/src/api/v1/meal/add_meal_to_shopping_list.py` [NEW]
- `services/api/src/api/v1/meal/__init__.py` [MODIFY] — export.
- `services/api/src/api/v1/meal_event/add_to_shopping_list.py` [NEW]
- `services/api/src/api/v1/meal_event/__init__.py` [MODIFY] — export.
- `services/api/src/routers/v1/meal_router.py` [MODIFY] — autocomplete + add-to-shopping-list mount.
- `services/api/src/routers/v1/meal_event_router.py` [MODIFY] — per-event add-to-shopping-list mount.
- `services/api/tests/test_add_meal_to_shopping_list.py` [NEW]
- `services/api/tests/test_add_meal_event_to_shopping_list.py` [NEW]

## Acceptance criteria

- `npx nx run api:lint` clean. ✓
- Full api suite: **2021 passed at 100% coverage**. ✓
- Autocomplete: `q=Kale` narrows results; blank-after-strip is a no-op; limit > 50 is silently capped.
- Per-Meal endpoint: happy, 404 (missing / archived), 403 (non-reader of Meal's book, non-writer of list), idempotent re-tap.
- Per-event endpoint: recipe-linked + Meal-linked paths; 422 on free-text; 404 on orphan recipe relationship; archived + orphan RecipeIngredient skipped cleanly.

## QA Walkthrough

See `mcal-5-qa-walkthrough.md`.
