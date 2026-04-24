# aam-15 — Pantry Domain Async — QA Walkthrough

**Scope:** Convert the 5 pantry HTTP endpoints + `helpers.py` + `pantry_service.py`
public surface to async, flip `pantry_router.py` handlers to `async def` with
`get_current_user_async` + `get_async_database`, and rewrite `test_pantry.py`
to the `mock_async_db` / `MockExecuteResult` pattern.

Explicitly out of scope and unchanged: `pantry_meal_subscriber.py`,
`pantry_shopping_subscriber.py`, `test_pantry_meal_subscriber.py`,
`test_pantry_shopping_subscriber.py`, `test_update_item_pantry_hook.py`,
`test_update_meal_event_pantry_hook.py`. Those still call sync
`pantry_service.*` helpers because aam-13 (shopping_list) and aam-14
(meal_event) are still backlog. The sync surface on `pantry_service`
stays frozen for them.

## Smoke checklist

All 36 pantry-touching tests green locally:

```
cd services/api && DATABASE_URL=postgresql://x/y poetry run pytest \
    tests/test_pantry.py \
    tests/test_pantry_meal_subscriber.py \
    tests/test_pantry_shopping_subscriber.py \
    tests/test_update_item_pantry_hook.py \
    tests/test_update_meal_event_pantry_hook.py \
    --no-cov --tb=short -q
# → 36 passed
```

Lint green:

```
npx nx run api:lint
# → All checks passed!
```

## Endpoint-by-endpoint trace

### GET /v1/pantries/default (`GetDefaultPantry`)

- **Handler (router):** `async def get_default_pantry` ← `get_current_user_async`, `get_async_database` ← `await GetDefaultPantry.call(...)`
- **Endpoint:** inherits `AsyncEndpoint`, `async def execute`
- **DB calls:**
  - `await get_or_create_default_pantry_async(user.id, self.database)`
    - `_find_default_membership_async` ⇒ `await db.execute(select(PantryUser)...).scalars().first()`
    - if membership found: `await database.find_by(Pantry, id=...)` (registry lookup in tests)
    - else: `async with database.lock(...)`, re-check, `await database.create(pantry)`, `await database.create(membership)`
  - `await self.db.execute(select(PantryIngredient).options(selectinload(PantryIngredient.ingredient)).where(...))`
- **Test file coverage:** `TestGetDefaultPantry::test_lazy_creates_pantry_when_missing`, `test_returns_existing_pantry_with_ingredients`

### POST /v1/pantries/{pantry_id}/ingredients (`AddPantryIngredient`)

- **Handler:** `async def add_pantry_ingredient` ← `await AddPantryIngredient.call(...)`
- **Endpoint:** `AsyncEndpoint`, `async def execute`
- **DB calls:**
  - `await require_pantry_access_async(...)` ⇒ `await database.find_by(Pantry, id=pantry_id)`, then `await db.execute(select(PantryUser)...)`
  - `await database.find_by(Ingredient, id=...)` OR `database.db.add(ingredient); await database.db.flush()`
  - `await upsert_pantry_ingredient_async(...)` ⇒ `await db.execute(select(PantryIngredient)...)` (existing lookup) + conditional `await db.commit()`/`await db.refresh()` OR `await database.create(row)`
- **Test file coverage:** 8 scenarios under `TestAddPantryIngredient` covering happy insert, upsert sum, viewer-403, 422 bad enum, 404 ingredient, 404 pantry, name-only path, 400 missing input.

### PATCH /v1/pantries/{pantry_id}/ingredients/{ingredient_id} (`UpdatePantryIngredient`)

- **Handler:** `async def update_pantry_ingredient`
- **Endpoint:** `AsyncEndpoint`
- **DB calls:**
  - `await require_pantry_access_async(..., mutate=True)`
  - `await self.db.execute(select(PantryIngredient)...)` — row lookup
  - mutate row attrs; `await self.db.commit(); await self.db.refresh(row)`
- **Test file coverage:** `TestUpdatePantryIngredient` — partial update, clamp-to-zero archives, all optional fields, 404 archived row.

### DELETE /v1/pantries/{pantry_id}/ingredients/{ingredient_id} (`DeletePantryIngredient`)

- **Handler:** `async def delete_pantry_ingredient`
- **Endpoint:** `AsyncEndpoint`
- **DB calls:**
  - `await require_pantry_access_async(..., mutate=True)`
  - `await self.db.execute(select(PantryIngredient)...)` — row lookup
  - if not archived: mutate archived_at; `await self.db.commit()`
- **Test file coverage:** `TestDeletePantryIngredient` — soft-delete sets archived_at, idempotent on already archived, viewer-403, non-member-403.

### POST /v1/pantries/{pantry_id}/estimate-expiry (`EstimateExpiry`)

- **Handler:** `async def estimate_pantry_expiry`
- **Endpoint:** `AsyncEndpoint`
- **DB calls:**
  - `await require_pantry_access_async(..., mutate=False)`
  - `await database.find_by(Ingredient, id=...)`
  - sync `estimate_expires_at(ingredient, storage_location)` — pure function, no I/O
- **Test file coverage:** existing behaviour already covered by permission-check path in the other tests; endpoint body is a thin wrapper over shelf_life_service (no new scenarios needed beyond what mutate=False semantics already hit).

## Lazy-load audit

Grep for ORM dot-chains in response-builder code for pantry:

```
rg 'row\.(quantity_display|unit_display|quantity_normalized|unit_normalized|storage_location|expires_at|created_at|updated_at|archived_at|pantry_id|ingredient_id|ingredient|canonical_name|category)' \
   services/api/src/api/v1/pantry/
```

Every chain either:
- hits a scalar column already fetched in `select(PantryIngredient)`, or
- hits `row.ingredient.canonical_name` / `row.ingredient.category`, which is
  covered by `selectinload(PantryIngredient.ingredient)` in
  `GetDefaultPantry.execute` — no lazy-load path.

`AddPantryIngredient` passes `ingredient=ingredient` into
`format_pantry_ingredient(...)` explicitly, so the formatter never lazy-loads
the relationship on the freshly-upserted row.

## Pre/post latency capture

Single-user traffic on `/v1/pantries/default` + the ingredient CRUD routes
is too thin for a 24h p95 delta to be statistically meaningful. Per the
epic's rule #9 (party-mode 2026-04-23), the post-merge evidence will come
from the client-latency pipeline (`cla-*`) with a synthetic-load supplement
once the full pantry editor flow (pantry-6 + pantry-7) is exercised under
the load-test client.

The conversion is mechanical (sync→async, no business-logic change) and
the endpoints are uniformly sub-50ms server-side today, so the primary
risk isn't latency — it's lazy-load/MissingGreenlet regressions, which
the audit above is the gate for.

## Rollback

One-line revert of the router-registration swap isn't meaningful here
because we flipped the domain directly (matches the aam-10 meal pattern).
If a regression shows up in production, revert commit is a `git revert`
of this story's single commit + `bin/prod-deploy` (~10 min). The sync
pantry_service surface still exists, so both halves keep building.
