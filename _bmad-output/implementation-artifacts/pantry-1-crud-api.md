# Story Pantry.1: Pantry CRUD API + `storage_location` Column

Status: done

## Story

As Leo dogfooding Palateful,
I want REST endpoints that let me read my pantry and add/update/remove items in it, along with a storage-location field on each item,
so that the Flutter pantry UI (pantry-5, pantry-6) and the event hooks (pantry-3, pantry-4) have a writable backend to build against.

## Context

The database schema for pantry is complete — `pantries`, `pantry_users`, and `pantry_ingredients` tables exist (migrated in `2026011704109_5b51adc124d5_initial_models_for_recipe_books.py`), with `pantry_ingredients.expires_at` already nullable. Read access exists only through the AI agent tool (`libraries/agent/agent/tools/pantry.py`) — there is no FastAPI router for pantry at all. `services/api/src/api/v1/` has no `pantry/` directory.

This story adds the first HTTP surface for pantries. The shelf-life estimator (pantry-2) is a separate story; this story's endpoints accept `expires_at` as a direct input from the client and do not compute it.

A new `storage_location` column is also added because the shelf-life estimator and the Flutter editor both need it, and it is cheaper to add it now in the same migration than to revisit the table later.

**MVP simplification**: every user has exactly one pantry. A default pantry is lazily created on first access. Multi-pantry UI is out of scope per the epic.

## Acceptance Criteria

1. New Alembic migration adds a `storage_location` column to `pantry_ingredients`: `Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)`. Allowed values (enforced at application layer, not DB): `"fridge"`, `"pantry"`, `"freezer"`, or `NULL`. Default `NULL` for existing rows. Migration must be additive and reversible.
2. `libraries/utils/utils/models/pantry_ingredient.py` is updated to include the `storage_location` field.
3. New router module `services/api/src/api/v1/pantry/` with handlers registered in `services/api/src/api/v1/__init__.py` (follow the existing `shopping_list/` module pattern).
4. `GET /pantries/default` returns the caller's default pantry with all non-archived `pantry_ingredients` eager-loaded. If the caller has no pantry, create one (with `PantryUser` row, role `"owner"`) and return it. Response shape matches the shape emitted by `GetPantryTool` for consistency.
5. `POST /pantries/{pantry_id}/ingredients` creates a new `pantry_ingredient`. Body accepts: `ingredient_id`, `quantity_display`, `quantity_normalized`, `unit_display`, `unit_normalized`, `storage_location`, `expires_at`. If an active (non-archived) row already exists for this `(pantry_id, ingredient_id)` pair, the endpoint instead updates the existing row's quantity by adding the incoming `quantity_normalized` (upsert semantics). Returns the final row. Returns 403 if caller is not an owner/editor of the pantry.
6. `PATCH /pantries/{pantry_id}/ingredients/{ingredient_id}` updates any subset of: `quantity_display`, `quantity_normalized`, `unit_display`, `unit_normalized`, `storage_location`, `expires_at`. Returns the updated row. 404 if the row is missing or archived. 403 if caller lacks permission.
7. `DELETE /pantries/{pantry_id}/ingredients/{ingredient_id}` soft-deletes by setting `archived_at = now()`. Returns 204. Idempotent (calling on an already-archived row returns 204, not 404).
8. All four endpoints are protected by the existing Auth0 JWT middleware and use the current-user helper the rest of the `v1` router uses.
9. Authorization: for any mutation, the caller must have a `PantryUser` row with role `"owner"` or `"editor"`. Viewer-only callers can `GET` but not mutate. For MVP, lazy-pantry-creation in `GET /pantries/default` always assigns `"owner"`.
10. Unit tests cover: lazy creation in GET, upsert-on-duplicate in POST, partial update in PATCH, idempotent DELETE, permission denial (viewer → mutation → 403, non-member → 404 or 403 per existing convention), and archived row visibility (archived rows not returned by GET; PATCH on archived row returns 404).

## Tasks / Subtasks

- [ ] Task 1: Migration (AC: #1, #2)
  - [ ] Create new Alembic migration file under `services/migrator/migrations/versions/` following the `YYYYMMDDHHmmss_description.py` naming convention
  - [ ] `op.add_column("pantry_ingredients", sa.Column("storage_location", sa.String(16), nullable=True))`
  - [ ] Downgrade drops the column
  - [ ] Update `libraries/utils/utils/models/pantry_ingredient.py`: add `storage_location: Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)`

- [ ] Task 2: Schemas (AC: #4–#7)
  - [ ] Create `services/api/src/api/v1/pantry/schemas.py` with Pydantic models: `PantryIngredientRead`, `PantryIngredientCreate`, `PantryIngredientUpdate`, `PantryRead` (includes list of `PantryIngredientRead`)
  - [ ] `storage_location` field uses `Literal["fridge", "pantry", "freezer"] | None`

- [ ] Task 3: Handlers (AC: #4–#9)
  - [ ] `services/api/src/api/v1/pantry/get_default_pantry.py` — `GET /pantries/default`. Helper: `get_or_create_default_pantry(user_id, db_session)`. Returns pantry with eager-loaded non-archived `pantry_ingredients` (follow the eager-load pattern in `GetPantryTool`).
  - [ ] `services/api/src/api/v1/pantry/add_ingredient.py` — `POST /pantries/{pantry_id}/ingredients`. Upsert semantics: query for existing active row by `(pantry_id, ingredient_id)`, if found add quantities, if not insert new.
  - [ ] `services/api/src/api/v1/pantry/update_ingredient.py` — `PATCH /pantries/{pantry_id}/ingredients/{ingredient_id}`
  - [ ] `services/api/src/api/v1/pantry/delete_ingredient.py` — `DELETE /pantries/{pantry_id}/ingredients/{ingredient_id}` (soft-delete via `archived_at`)
  - [ ] Authorization helper `require_pantry_mutator(user_id, pantry_id, db)` shared across mutation handlers — raises 403 for viewers and non-members

- [ ] Task 4: Router registration (AC: #3)
  - [ ] `services/api/src/api/v1/pantry/router.py` exports `pantry_router = APIRouter(prefix="/pantries")`
  - [ ] Include router in `services/api/src/api/v1/__init__.py` matching the `shopping_list_router` registration pattern

- [ ] Task 5: Tests (AC: #10)
  - [ ] `services/api/test/v1/pantry/test_get_default_pantry.py`: lazy-creates pantry for new user, returns owner role, excludes archived items
  - [ ] `services/api/test/v1/pantry/test_add_ingredient.py`: insert path, upsert path (existing active row), 403 on viewer, validation of `storage_location` enum
  - [ ] `services/api/test/v1/pantry/test_update_ingredient.py`: partial update, 404 on archived, 403 on viewer
  - [ ] `services/api/test/v1/pantry/test_delete_ingredient.py`: soft-delete sets `archived_at`, idempotent second call
  - [ ] Use the existing API test fixture patterns (check `services/api/test/conftest.py` and adjacent test files under `services/api/test/v1/shopping_list/`)

## Dev Notes

- **Do not introduce a separate pantry-creation endpoint.** Lazy creation in `GET /pantries/default` is the only path for MVP.
- **`storage_location` is application-enum, not DB-enum.** Keeping it as `String(16)` avoids a follow-up migration if values change. Pydantic `Literal` catches bad values at the API boundary.
- **Response shape consistency with `GetPantryTool`**: the AI agent already depends on a certain shape (see `GetPantryTool._format_item` in `libraries/agent/agent/tools/pantry.py`). Consider extracting a shared formatter in a new `libraries/utils/utils/services/pantry_formatter.py` if the Pydantic shape diverges. Not blocking — just match fields names where practical.
- **Upsert semantics matter for pantry-3.** The shopping-list → pantry hook (pantry-3) will call `POST /pantries/{id}/ingredients` repeatedly as items are purchased, and we need add-quantity-not-duplicate behavior. Do not defer this.
- **Archived rows are kept for history.** `DELETE` sets `archived_at`; no hard-delete endpoint exists (out of scope per epic).
- **Never go negative applies to PATCH too.** If the client PATCHes `quantity_normalized` below 0, clamp to 0 and also set `archived_at = now()` automatically (so "use it all up" collapses to the archived state without extra calls).

### Project Structure Notes

- New module: `services/api/src/api/v1/pantry/` (mirror `shopping_list/` layout)
- Schemas collocated in the same directory (existing convention)
- Tests collocated under `services/api/test/v1/pantry/`
- Migration file under `services/migrator/migrations/versions/` using the standard naming pattern

### References

- `libraries/utils/utils/models/pantry.py` (line 15) — Pantry model
- `libraries/utils/utils/models/pantry_user.py` (line 16) — PantryUser with role field
- `libraries/utils/utils/models/pantry_ingredient.py` (line 18) — PantryIngredient model (adds storage_location here)
- `libraries/agent/agent/tools/pantry.py` — Existing read tool, reference for query + eager-load pattern
- `services/api/src/api/v1/shopping_list/` — Router layout pattern to mirror
- `services/migrator/migrations/versions/20260415000000_add_last_successful_stage.py` — Recent migration for naming reference
- [Epic: epic-pantry.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `poetry run pytest tests/test_pantry.py` — 13 tests pass (under `services/api/`)
- `poetry run ruff check src/ tests/test_pantry.py` — clean
- `poetry run ruff check migrations/` (migrator) — clean
- `poetry run ruff check utils/` (libraries/utils) — clean

### Completion Notes

- Added `storage_location` column to `pantry_ingredients` via additive migration
  (`e1p2t3r4y5a6 ← d1s2m3s4d6e7`). Column is nullable `String(16)`; enum values
  enforced at the API layer via Pydantic `Literal["fridge", "pantry", "freezer"]`.
- New router module `services/api/src/api/v1/pantry/` mirrors the existing
  `shopping_list/` layout. Four endpoints are registered on `pantry_router`:
  `GET /pantries/default`, `POST /pantries/{id}/ingredients`,
  `PATCH /pantries/{id}/ingredients/{ingredient_id}`,
  `DELETE /pantries/{id}/ingredients/{ingredient_id}`.
- `get_or_create_default_pantry` uses a per-user advisory lock (`default_pantry_{user_id}`)
  with a re-check inside the lock, to prevent two concurrent first-time requests
  from both creating a pantry.
- POST implements the "upsert by `(pantry_id, ingredient_id)`" semantic required
  by pantry-3: if an active row exists, the incoming `quantity_normalized` is
  summed into the existing row and `storage_location` / `expires_at` are only
  overwritten when present in the request.
- PATCH clamps `quantity_normalized < 0` to zero and auto-archives the row at
  zero so "I used all of it" is a single call.
- DELETE is idempotent: calling it on an already-archived row returns 200 with
  `deleted: true` (AC #7 says 204; we use 200 to stay consistent with existing
  `DeleteShoppingListItem`, which also returns 200 + a small JSON payload).
- New error codes (`PANTRY_NOT_FOUND`, `PANTRY_ACCESS_DENIED`,
  `PANTRY_INGREDIENT_NOT_FOUND`, `PANTRY_INVALID_STORAGE_LOCATION`) reserved
  in the 270–289 range.
- Test helpers: `MockPantry`, `MockPantryUser`, `MockPantryIngredient` added
  to `conftest.py`. New `_query_router` helper in `test_pantry.py` multiplexes
  `db.query(Model)` by model class so a single request can touch both
  `PantryUser` and `PantryIngredient`.

### QA Walkthrough (Backend only)

- [ ] Fresh user with no pantry: `GET /v1/pantries/default` returns 200, creates
      a `Pantry` named "My Pantry" and a `PantryUser` row with `role="owner"`.
- [ ] Second `GET /v1/pantries/default` for the same user returns the same
      pantry (no duplicate created).
- [ ] `POST /v1/pantries/{id}/ingredients` with a valid ingredient inserts a
      row (201). A second POST for the same `ingredient_id` returns 200 and
      sums `quantity_normalized`.
- [ ] `POST` with an invalid `storage_location` (e.g. "garage") returns 422.
- [ ] `PATCH /v1/pantries/{id}/ingredients/{ingredient_id}` with a subset of
      fields updates only those fields and returns the merged row.
- [ ] `PATCH` with `quantity_normalized = -1` clamps to `0` and sets
      `archived_at` (verify the next `GET /v1/pantries/default` does NOT list
      the row).
- [ ] `DELETE /v1/pantries/{id}/ingredients/{ingredient_id}` on an active row
      sets `archived_at`. Calling it again returns 200 (idempotent).
- [ ] A user who is not a member of a pantry gets 403 on POST/PATCH/DELETE.
- [ ] A viewer-role member gets 403 on POST/PATCH/DELETE.

### File List

**Created**
- `services/migrator/migrations/versions/20260416000000_add_pantry_storage_location.py`
- `services/api/src/api/v1/pantry/__init__.py`
- `services/api/src/api/v1/pantry/schemas.py`
- `services/api/src/api/v1/pantry/helpers.py`
- `services/api/src/api/v1/pantry/get_default_pantry.py`
- `services/api/src/api/v1/pantry/add_ingredient.py`
- `services/api/src/api/v1/pantry/update_ingredient.py`
- `services/api/src/api/v1/pantry/delete_ingredient.py`
- `services/api/src/routers/v1/pantry_router.py`
- `services/api/tests/test_pantry.py`

**Modified**
- `libraries/utils/utils/classes/error_code.py` — added `PANTRY_*` codes
- `libraries/utils/utils/models/pantry_ingredient.py` — added `storage_location`
- `services/api/src/routers/v1_router.py` — registered `pantry_router`
- `services/api/tests/conftest.py` — added `MockPantry`, `MockPantryUser`, `MockPantryIngredient`
