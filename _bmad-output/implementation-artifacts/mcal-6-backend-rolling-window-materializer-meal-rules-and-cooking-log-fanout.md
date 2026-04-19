# Story mcal-6 — Backend: materializer Meal-rule support + cooking-log fan-out

**Status:** done
**Epic:** epic-meals-calendar
**Depends on:** mcal-1 (meal_id columns), mcal-3 (XOR-aware endpoints).

## Scope

### 1. Materializer

- `_resolve_title` gains a `rule.meal_id` branch that queries `Meal.name`. Meal wins over Recipe when both are unexpectedly set (defense in depth — XOR is schema-enforced upstream). Falls through to `rule.title or "Meal"` when both lookups miss.
- `insert_values` dict propagates `meal_id` alongside `recipe_id`, and now also includes `calendar_id` (pre-existing NOT-NULL gap from cal-found-2; flagged in the handoff gotcha).

### 2. New `POST /v1/cooking-logs` handler

No prior production code wrote CookingLog rows. This story creates the canonical write path:

- **Recipe event** (`meal_event_id` with `recipe_id` set) → one row, `recipe_id` set, `meal_id=NULL`.
- **Meal event** (`meal_event_id` with `meal_id` set) → one parent row (`meal_id` set, `recipe_id=NULL`) + one child row per live component (`recipe_id` set, `parent_meal_log_id` = parent.id). Children preserve recipe-level "last cooked" history; parent row surfaces on the Meal detail screen.
- **Direct recipe** (`recipe_id` without `meal_event_id`) → one row, `recipe_id` set.
- Archived/null component recipes are skipped in the fan-out.
- Free-text events, both-set FKs, neither-set FKs → 422.

Caller auth:
- meal_event path gates on `require_calendar_access` (calendar membership).
- direct-recipe path only validates the recipe exists — this matches how `POST /v1/recipes/{id}/cooking-logs` would traditionally work; the endpoint is a thin logger.

### 3. Config

Default `cooked_at` is `datetime.utcnow()` when caller omits. `scale_factor` defaults to `Decimal("1.0")`.

## File List

- `libraries/utils/utils/recurrence/materializer.py` [MODIFY] — `_resolve_title` + `insert_values`.
- `libraries/utils/test/test_materializer.py` [MODIFY] — 4 new `_resolve_title` tests + `meal_id: None` default on `_make_rule`.
- `services/api/src/api/v1/cooking_log/create_cooking_log.py` [NEW]
- `services/api/src/api/v1/cooking_log/__init__.py` [MODIFY] — export.
- `services/api/src/routers/v1/cooking_log_router.py` [MODIFY] — `POST /v1/cooking-logs` mount.
- `services/api/tests/test_create_cooking_log.py` [NEW] — 13 tests covering every branch.

## Acceptance criteria

- `npx nx run api:lint` + `npx nx run utils:lint` clean. ✓
- `npx nx run api:test`: **2032 passed at 100% coverage**. ✓
- utils suite: **259 passed**, including 4 new materializer tests. ✓
- Materialized Meal-rule events inherit `meal_id` and render the Meal's name as title.
- Cooking-log fan-out: single user action creates 1 parent + N children; archived components gracefully skipped; recipe-level "last cooked" queries count the fan-out children.

## QA Walkthrough

See `mcal-6-qa-walkthrough.md`.
