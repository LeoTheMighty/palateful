# Story mcv-3: Backend — component add/remove/reorder + favorite

**Status:** done
**Epic:** epic-meals-create-and-view

## Goal

Ship the four mutation endpoints the Flutter edit-mode needs, plus a
favorite toggle for the Meal detail action bar.

## Scope

### Handlers (`services/api/src/api/v1/meal/`)

- `add_recipe_to_meal.py` — `POST /v1/meals/{id}/recipes`.
  `MealComponentAddRequest { recipe_id, order_index? }`. Rejects
  duplicate with 409 (`MEAL_COMPONENT_DUPLICATE`). Rejects unreadable
  recipe with 404 (`MEAL_COMPONENT_UNREADABLE`). Default `order_index`
  is `max(existing) + 1`.
- `remove_recipe_from_meal.py` — `DELETE /v1/meals/{id}/recipes/{recipe_id}`.
  Rejects with 422 (`MEAL_MIN_COMPONENTS`) if the remove would drop below
  2 components. 404 (`MEAL_COMPONENT_NOT_FOUND`) if not on the meal.
- `reorder_meal_components.py` — `POST /v1/meals/{id}/reorder`.
  `MealReorderRequest { recipe_ids }` — schema rejects duplicates + <2.
  Service rejects set-mismatch with 422 (`MEAL_REORDER_MISMATCH`).
- `favorite_meal.py` — both `POST` and `DELETE /v1/meals/{id}/favorite`.
  Idempotent on both sides. Requires read membership, not write.

### Service layer (`libraries/utils/utils/services/meal_service.py`)

Extends MealService with:
- `add_component` — dup check → readability check → optional auto-order.
- `remove_component` — <2 guard + not-on-meal guard.
- `reorder_components` — set-mismatch guard + atomic order_index rewrite.
- `set_favorite` — idempotent upsert/delete of `meal_favorites` row.

New domain exceptions: `ComponentDuplicateError`,
`ComponentNotFoundError`, `MinComponentsError`, `ReorderMismatchError`.

### Schemas (`services/api/src/schemas/meal.py`)

Adds `MealComponentAddRequest`, `MealReorderRequest` (with unique
validator), and `MealFavoriteResponse`.

### Router (`services/api/src/routers/v1/meal_router.py`)

Adds five routes to the existing `meal_router`:
- `POST /meals/{id}/recipes`
- `DELETE /meals/{id}/recipes/{recipe_id}`
- `POST /meals/{id}/reorder`
- `POST /meals/{id}/favorite`
- `DELETE /meals/{id}/favorite`

## Acceptance Criteria

- [x] Four handlers land + are wired into the existing router.
- [x] Duplicate component → 409; unreadable → 404; non-writer → 403.
- [x] Removing at 2 → 422 `MEAL_MIN_COMPONENTS`.
- [x] Reorder set-mismatch → 422 `MEAL_REORDER_MISMATCH`; schema-level
      duplicate / <2 rejects → 422.
- [x] Favorite/unfavorite endpoints idempotent; require read membership.
- [x] 100% branch coverage across every new module.
- [x] `npx nx run api:lint` + `npx nx run api:test` pass.

## QA Walkthrough

See `mcv-3-qa-walkthrough.md`.

## File List

New:
- `services/api/src/api/v1/meal/add_recipe_to_meal.py`
- `services/api/src/api/v1/meal/remove_recipe_from_meal.py`
- `services/api/src/api/v1/meal/reorder_meal_components.py`
- `services/api/src/api/v1/meal/favorite_meal.py`
- `services/api/tests/test_meal_components.py`

Modified:
- `libraries/utils/utils/services/meal_service.py` — add_component /
  remove_component / reorder_components / set_favorite.
- `services/api/src/schemas/meal.py` — MealComponentAddRequest /
  MealReorderRequest / (MealFavoriteResponse already present).
- `services/api/src/api/v1/meal/__init__.py` — register new handlers.
- `services/api/src/routers/v1/meal_router.py` — add 5 routes.
