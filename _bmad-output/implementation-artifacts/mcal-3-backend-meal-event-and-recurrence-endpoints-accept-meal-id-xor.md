# Story mcal-3 — Backend: meal_event + recurrence_rule endpoints accept `meal_id` XOR `recipe_id`

**Status:** done
**Epic:** epic-meals-calendar
**Depends on:** mcal-1 (column + CHECK constraint shipped).

## Scope

Eight handlers gain symmetric `meal_id` support. Both surfaces (meal_events + meal_recurrence_rules) share the same three invariants, so helpers live in one module.

### Shared helpers

`services/api/src/api/v1/meal_event/_meal_binding.py` [NEW] owns:

- `validate_recipe_meal_xor(recipe_id, meal_id)` — raises `APIException(422, MEAL_EVENT_RECIPE_XOR_MEAL)` when both are set. The DB-level CHECK is the authoritative invariant; this is the clean error-code path.
- `require_meal_available(db, meal_id, user)` — wraps `api.v1.meal._access.require_meal_read` with an additional archive guard (archived meals return 404, not 200).
- `build_meal_summary(meal) -> MealSummary` — deterministic `{id, name, component_count, image_urls[:4]}` shape. Unavailable components (archived recipe/book, null relationship) contribute to `component_count` but drop their image URL so the collage renders a blank slot instead of a stale thumbnail.

### Handler changes

| Handler | Change |
|---|---|
| `create_meal_event.py` | accept `meal_id`; XOR gate; load + authorize Meal; return `meal_summary`. |
| `update_meal_event.py` | accept `meal_id`; XOR gate post-resolve; mode-switch sets one FK and clears the other; `meal_summary` rehydration. |
| `get_meal_event.py` | add `meal_id` + `meal_summary` to response (lazy-loaded via ORM relationship). |
| `list_meal_events.py` | `selectinload` chain `MealEvent.meal → Meal.components → MealRecipe.recipe` for O(1) queries regardless of list size. |
| `create_recurrence_rule.py` | accept `meal_id`; XOR gate; Meal-mode rules store `title=None` so the materializer derives the display title from the linked Meal at read time. |
| `update_recurrence_rule.py` | mode-switch in both `scope=all` and `scope=this_and_following`; new-rule inherits `meal_id` in split flow; meal-hydration on all four response paths. |
| `get_recurrence_rule.py` | fetch Meal + components when `rule.meal_id` set. |
| `list_recurrence_rules.py` | batch-fetch Meals referenced by Meal-linked rules via `Meal.id.in_(meal_ids)` — O(2) queries regardless of list size. |

### Schema updates

- `MealEventCreate/Update/Response` + `MealEventListItem`: `meal_id: str | None`, `meal_summary: MealSummary | None`.
- `RecurrenceRuleResponse`: `meal_id`, `meal_summary`.
- `_access.validate_recurrence_fields` now accepts `meal_id` as an alternative to `recipe_id` / `title`.

### Error code

`ErrorCode.MEAL_EVENT_RECIPE_XOR_MEAL = 135` (lives in the Meal Event block 130-139).

## File List

- `services/api/src/api/v1/meal_event/_meal_binding.py` [NEW]
- `services/api/src/api/v1/meal_event/create_meal_event.py` [MODIFY]
- `services/api/src/api/v1/meal_event/update_meal_event.py` [MODIFY]
- `services/api/src/api/v1/meal_event/get_meal_event.py` [MODIFY]
- `services/api/src/api/v1/meal_event/list_meal_events.py` [MODIFY]
- `services/api/src/api/v1/recurrence_rule/create_recurrence_rule.py` [MODIFY]
- `services/api/src/api/v1/recurrence_rule/update_recurrence_rule.py` [MODIFY]
- `services/api/src/api/v1/recurrence_rule/get_recurrence_rule.py` [MODIFY]
- `services/api/src/api/v1/recurrence_rule/list_recurrence_rules.py` [MODIFY]
- `services/api/src/api/v1/recurrence_rule/_access.py` [MODIFY] — `validate_recurrence_fields` accepts `meal_id`.
- `libraries/utils/utils/classes/error_code.py` [MODIFY] — `MEAL_EVENT_RECIPE_XOR_MEAL = 135`.
- `services/api/tests/conftest.py` [MODIFY] — `MockMealEvent` defaults `meal_id=None, meal=None`.
- `services/api/tests/test_recurrence_rule.py` [MODIFY] — `MockMealRecurrenceRule` defaults `meal_id=None`.
- `services/api/tests/test_meal_event_with_meals.py` [NEW] — XOR reject, meal-mode create/update/get/list, hydration edges, regression fixtures.
- `services/api/tests/test_recurrence_rule_with_meals.py` [NEW] — XOR reject, meal-mode create/update/get/list, split flow with meal_id, regression.

## Acceptance criteria

- `npx nx run api:lint` clean. ✓
- `npx nx run api:test` green: **2002 passed at 100% coverage**. ✓
- XOR reject returns 422 with code `MEAL_EVENT_RECIPE_XOR_MEAL` for both surfaces. ✓
- 404 on missing/archived Meal; 403 when user lacks read on Meal's book. ✓
- Recipe-only and free-text paths byte-identical to pre-epic shape (`meal_id: null, meal_summary: null` is additive — existing clients ignore unknown keys). ✓
- Mode switches cleanly (Recipe → Meal clears recipe_id; Meal → Recipe clears meal_id). ✓
- List hydration via `selectinload` so meal_summary doesn't N+1 the event list. ✓

## QA Walkthrough

See `mcal-3-qa-walkthrough.md`.
