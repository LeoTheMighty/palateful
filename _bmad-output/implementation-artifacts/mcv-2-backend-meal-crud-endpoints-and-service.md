# Story mcv-2: Backend — Meal CRUD + Service

**Status:** done
**Epic:** epic-meals-create-and-view

## Goal

Land the CRUD surface that every Flutter entry point leans on:

1. `POST /v1/recipe-books/{book_id}/meals` — create + validate.
2. `GET /v1/meals/{meal_id}` — hydrated Meal with component availability.
3. `GET /v1/meals` + `GET /v1/recipe-books/{book_id}/meals` — paginated.
4. `PATCH /v1/meals/{meal_id}` — name / description.
5. `POST /v1/meals/{meal_id}/archive` + `/restore`.

## Scope

### Handlers (`services/api/src/api/v1/meal/`)

Each subclass of `Endpoint`, auth-gated via shared `_access.py` helpers:

- `create_meal.py` — `require_book_write`, then
  `MealService.create_with_components` in one transaction; 404 on any
  unreadable component.
- `get_meal.py` — `require_meal_read`; marks components `available=false`
  when recipe archived or book unshared.
- `list_meals.py` — flat list across every readable book, paginated.
- `list_meals_in_book.py` — book-scoped list, excludes archived unless
  `include_archived=true`.
- `update_meal.py` — name / description only. Component edits route
  through dedicated endpoints in mcv-3.
- `archive_meal.py` / `restore_meal.py` — idempotent w/ 400 on illegal
  state; writes `service="audit"` ErrorLog per archive/restore.

### Service (`libraries/utils/utils/services/meal_service.py`)

`MealService` with the mcv-2-scoped methods: `get_with_components`
(`selectinload` chain Meal → MealRecipe → Recipe → RecipeBook),
`hydrate_components` (availability marking against archived recipes +
unshared / archived books), `create_with_components`, `archive`,
`restore`, plus the `user_has_book_read` / `user_has_book_write`
helpers. mcv-3 extends the service with `add_component` /
`remove_component` / `reorder_components` / `set_favorite`.

### Schemas (`services/api/src/schemas/meal.py`)

`MealCreateRequest` (≥2 unique component_recipe_ids), `MealUpdateRequest`,
`MealComponentResponse` (with `available` + `last_known_name`),
`MealResponse`, `MealSummaryResponse` (grid-tile shape), `MealListResponse`,
`MealArchiveResponse`. mcv-3 adds `MealComponentAddRequest`,
`MealReorderRequest`, `MealFavoriteResponse`.

### Router + wire-in

- `services/api/src/routers/v1/meal_router.py` — defines `meal_router`
  (`/v1/meals/...`) + `book_meal_router` (`/v1/recipe-books/.../meals`).
- `v1_router.py` registers both.

### ErrorCodes

Reserved the `300-319` range in `libraries/utils/utils/classes/error_code.py`
for the Meal feature — mcv-2 uses `MEAL_NOT_FOUND`, `MEAL_ACCESS_DENIED`,
`MEAL_COMPONENT_UNREADABLE`, `MEAL_ALREADY_ARCHIVED`, `MEAL_NOT_ARCHIVED`.
The rest (`MEAL_COMPONENT_DUPLICATE`, `MEAL_MIN_COMPONENTS`,
`MEAL_REORDER_MISMATCH`, `MEAL_COMPONENT_UNAVAILABLE`,
`MEAL_COMPONENT_NOT_FOUND`) land in mcv-3.

### Tests

- `test_meal_service.py` — 20 cases for `hydrate_components`,
  availability branches (archived recipe / unshared book / archived
  book / missing recipe relationship), `user_has_book_*`,
  `_ensure_components_readable`, `create_with_components`, archive /
  restore.
- `test_meal_router.py` — HTTP tests per handler: happy paths, 403
  (non-member + viewer-for-write), 404, schema validation errors
  (<2 components + duplicate component_id), archive idempotency.

## Acceptance Criteria

- [x] Seven handlers live under `services/api/src/api/v1/meal/`.
- [x] All responses hydrate via `selectinload` (`Meal.components →
      MealRecipe.recipe → Recipe.recipe_book`).
- [x] `hydrate_components` marks `available=false` on archived recipes
      and on recipes whose book is not readable by the caller.
- [x] Archive / restore write `service="audit"` ErrorLog rows.
- [x] Every mutation asserts write-level book membership (owner /
      editor); reads accept any role including viewer.
- [x] 100% branch coverage across every new module.
- [x] `npx nx run api:lint` + `npx nx run api:test` both pass.

## QA Walkthrough

See `mcv-2-qa-walkthrough.md`.

## File List

New:
- `services/api/src/schemas/meal.py`
- `libraries/utils/utils/services/meal_service.py`
- `services/api/src/api/v1/meal/__init__.py`
- `services/api/src/api/v1/meal/_access.py`
- `services/api/src/api/v1/meal/_response.py`
- `services/api/src/api/v1/meal/archive_meal.py`
- `services/api/src/api/v1/meal/create_meal.py`
- `services/api/src/api/v1/meal/get_meal.py`
- `services/api/src/api/v1/meal/list_meals.py`
- `services/api/src/api/v1/meal/list_meals_in_book.py`
- `services/api/src/api/v1/meal/restore_meal.py`
- `services/api/src/api/v1/meal/update_meal.py`
- `services/api/src/routers/v1/meal_router.py`
- `services/api/tests/test_meal_router.py`
- `services/api/tests/test_meal_service.py`

Modified:
- `services/api/src/routers/v1_router.py` — include meal routers.
- `libraries/utils/utils/classes/error_code.py` — add `300-319`.
