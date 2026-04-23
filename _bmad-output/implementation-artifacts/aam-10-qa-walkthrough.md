# aam-10 QA Walkthrough — Meal Domain Async

**Story**: aam-10 (Meal domain async)
**Epic**: epic-api-async-migration
**Last-good commit (pre-aam-10)**: `8109688` — `feat(api): aam-6 — async auth deps + race-test scaffolding`
**Rollback procedure**: `git revert <aam-10-commit> && bin/prod-deploy` (~10 min). aam-10 does NOT mount a `/_legacy_v1/meals` sibling — see Section 4.

This walkthrough has four sections, in the order the runbook prescribes:

1. Lazy-load audit
2. Pre-merge latency baseline
3. Manual scenario checklist
4. Dual-register deviation call-out + cross-domain blast radius

---

## 1. Lazy-load Audit

Goal: every ORM `.<attr>.<attr>` chain reachable from a meal-domain handler
is covered by a `selectinload(...)` chain on the originating query, so no
attribute access fires `MissingGreenlet` on the async engine.

### 1.1 Grep — attribute chains in `services/api/src/api/v1/meal/` and the
shared service module

```bash
rg -nE '(comp|mc)\.(recipe|recipe_id|recipe_book|order_index|book)' \
    services/api/src/api/v1/meal/ libraries/utils/utils/services/meal_service.py \
    --glob '!*test*' --glob '!*__pycache__*'

services/api/src/api/v1/meal/get_public_meal_by_token.py:50:    recipe: Recipe | None = mc.recipe
libraries/utils/utils/services/meal_service.py:261:    recipe = comp.recipe
libraries/utils/utils/services/meal_service.py:268:        recipe_id=str(comp.recipe_id),
libraries/utils/utils/services/meal_service.py:269:        order_index=comp.order_index,
libraries/utils/utils/services/meal_service.py:292:        order_index=comp.order_index,
```

```bash
rg -nE 'recipe\.(recipe_book|name|image_url|prep_time|cook_time|archived_at|share_token|ingredients)' \
    services/api/src/api/v1/meal/ libraries/utils/utils/services/meal_service.py \
    --glob '!*test*' --glob '!*__pycache__*'

services/api/src/api/v1/meal/get_public_meal_by_token.py:53:    if recipe.archived_at is not None
services/api/src/api/v1/meal/get_public_meal_by_token.py:55:    has_token = recipe.share_token is not None
services/api/src/api/v1/meal/get_public_meal_by_token.py:58:    name=recipe.name
services/api/src/api/v1/meal/get_public_meal_by_token.py:59:    image_url=recipe.image_url
services/api/src/api/v1/meal/get_public_meal_by_token.py:61:    public_token=recipe.share_token
services/api/src/api/v1/meal/add_meal_to_shopping_list.py:46:    # comment — meal.components[i].recipe.ingredients
libraries/utils/utils/services/meal_service.py:123:    if recipe.archived_at is not None
libraries/utils/utils/services/meal_service.py:129:    book = recipe.recipe_book
libraries/utils/utils/services/meal_service.py:139:    [ri for ri in recipe.ingredients if ri.archived_at is None]
libraries/utils/utils/services/meal_service.py:281:    book = recipe.recipe_book
libraries/utils/utils/services/meal_service.py:282:    book_readable = str(recipe.recipe_book_id) in readable
libraries/utils/utils/services/meal_service.py:284:    recipe.archived_at is None
libraries/utils/utils/services/meal_service.py:293:    name=recipe.name if available else ""
libraries/utils/utils/services/meal_service.py:294:    image_url=recipe.image_url if available else None
libraries/utils/utils/services/meal_service.py:295:    prep_time=recipe.prep_time if available else None
libraries/utils/utils/services/meal_service.py:296:    cook_time=recipe.cook_time if available else None
libraries/utils/utils/services/meal_service.py:299:    last_known_name=None if available else recipe.name
```

### 1.2 Per-chain coverage

| Chain                                            | Origin query                                                                    | selectinload coverage                                                                         |
|--------------------------------------------------|---------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `meal.components[i].order_index` (scalar on `MealRecipe`) | `MealService.get_with_components`, `list_meals`, `list_meals_in_book`, `get_public_meal_by_token` | `selectinload(Meal.components)` — eager-loads the join rows; scalar columns ride along. |
| `meal.components[i].recipe` (FK → Recipe)        | same as above                                                                   | `selectinload(MealRecipe.recipe)` chained off `Meal.components`.                              |
| `meal.components[i].recipe.recipe_book` (FK → RecipeBook) | `get_with_components`, `list_meals`, `list_meals_in_book`, recipe-domain `list_meals_using_recipe`, `list_favorites` | `selectinload(Recipe.recipe_book)` chained off `MealRecipe.recipe`.                        |
| `meal.components[i].recipe.recipe_book.archived_at` (scalar) | same                                                                            | covered transitively by the `Recipe.recipe_book` selectinload (scalar column on RecipeBook). |
| `meal.components[i].recipe.recipe_book.name` (scalar) | same                                                                            | same as above.                                                                                |
| `meal.components[i].recipe.{name,image_url,prep_time,cook_time,archived_at,share_token,recipe_book_id}` (scalars on Recipe) | same                                                                            | covered by `MealRecipe.recipe` selectinload.                                                  |
| `meal.components[i].recipe.ingredients[j].ingredient` (FK → Ingredient) | `add_meal_to_shopping_list` (re-hydrate query)                                  | `selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)` — explicitly chained in `AddMealToShoppingList.execute` for `aggregate_meal_ingredients`. |
| `meal.components[i].recipe.ingredients[j].{quantity_display,unit_display,archived_at}` (scalars on RecipeIngredient) | same                                                                            | scalar columns ride along the `Recipe.ingredients` selectinload.                              |
| `meal.{name,description,recipe_book_id,archived_at,created_at,updated_at,share_token,id}` (scalars on Meal) | every meal-domain query                                                         | scalar columns; no eager-load needed.                                                         |

**Result**: every chain in the response-builder + endpoint paths is covered. No `MissingGreenlet` risk identified.

### 1.3 Sync-callsite carve-outs

Two callsites stay sync after aam-10 and intentionally don't use the async `selectinload` chains above:

- `aggregate_meal_ingredients(meal, session)` — module-level function in `meal_service.py`. Walks the eager-loaded component tree (no DB call on the hot path) and calls `normalize_unit_display(token, session)` (memory-only when the unit-alias cache is pre-warmed at lifespan start). Worker + parser still build against this sync surface — see runbook §"Sync surface" whitelist.
- `meal_event/_meal_binding.require_meal_available(db, meal_id, user)` — sync helper used by the still-sync meal_event + recurrence_rule handlers. aam-10 inlined the sync `db.query(Meal).options(selectinload(...))` chain here so it doesn't depend on the now-async `meal/_access.require_meal_read`. See Section 4 for context.

---

## 2. Pre-merge Latency Baseline

> **Action required before merge**: run from a workstation with prod AWS
> credentials configured. The output during the walkthrough author's
> session was empty (Session Manager returned EOF on connect — likely
> a credential / VPN setup issue local to the author's machine, not a
> defect of the script).

```bash
bin/prod-script services/api/scripts/analyze_latency.py \
    --window 24h --format table 2>&1 | \
    grep -E '^GET|^POST|^PATCH|^DELETE' | \
    grep -E '/v1/meals|/v1/recipe-books/[^/]+/meals|/v1/recipes/[^/]+/meals|/v1/favorites'
```

Capture the table here before opening the PR. Target rows (one per
`(method, normalized_path)`):

| method | normalized_path                              | count | p50_ms | p95_ms | p99_ms | max_ms |
|--------|-----------------------------------------------|-------|--------|--------|--------|--------|
| GET    | /v1/meals                                     |       |        |        |        |        |
| GET    | /v1/meals/:id                                 |       |        |        |        |        |
| GET    | /v1/meals/public/:token                       |       |        |        |        |        |
| POST   | /v1/meals                                     |       |        |        |        |        |
| PATCH  | /v1/meals/:id                                 |       |        |        |        |        |
| POST   | /v1/meals/:id/share                           |       |        |        |        |        |
| POST   | /v1/meals/:id/favorite                        |       |        |        |        |        |
| DELETE | /v1/meals/:id/favorite                        |       |        |        |        |        |
| POST   | /v1/meals/:id/components                      |       |        |        |        |        |
| DELETE | /v1/meals/:id/components/:rid                 |       |        |        |        |        |
| POST   | /v1/meals/:id/components/reorder              |       |        |        |        |        |
| POST   | /v1/meals/:id/archive                         |       |        |        |        |        |
| POST   | /v1/meals/:id/restore                         |       |        |        |        |        |
| POST   | /v1/meals/:id/add-to-shopping-list            |       |        |        |        |        |
| GET    | /v1/recipe-books/:id/meals                    |       |        |        |        |        |
| GET    | /v1/recipes/:id/meals                         |       |        |        |        |        |
| GET    | /v1/favorites                                 |       |        |        |        |        |

**Post-merge target (per AC 10)**: client-observed p95 on `GET /v1/meals/{meal_id}` < 500 ms after a 24-hour observation window. Capture the same table 24 h after deploy and diff the p95 column row-by-row. Any row whose recent p95 > 1.5 × baseline p95 is a regression — investigate before closing the observation window.

For low-traffic endpoints (e.g. `POST /v1/meals/:id/share` — single-user
production), supplement the natural-traffic baseline with a synthetic
load run via `tools/load_test_client_latencies.py` per the runbook's
synthetic-load supplement guidance.

---

## 3. Manual Scenario Checklist (9 + MCP)

Run these against staging after the PR lands; each row is a one-shot
assertion the converted async path returns the same shape + status the
sync path returned. Setup once (curl token in `$TOKEN`, base in `$API`):

```bash
TOKEN=...
API=https://staging.api.palateful.com
```

| # | Scenario              | Endpoint                                                      | Expect                                                       |
|---|-----------------------|---------------------------------------------------------------|--------------------------------------------------------------|
| 1 | create                | `POST $API/v1/recipe-books/$BOOK/meals -d '{"name":"X","recipe_ids":[$R1,$R2]}'` | 201, `{id, name, components[2]}`                            |
| 2 | read                  | `GET $API/v1/meals/$M`                                       | 200, full `MealResponse` (components hydrated, `is_favorite`)|
| 3 | update                | `PATCH $API/v1/meals/$M -d '{"name":"Y"}'`                   | 200, name updated                                            |
| 4 | add-recipe            | `POST $API/v1/meals/$M/components -d '{"recipe_id":$R3}'`    | 201                                                          |
| 5 | remove-recipe         | `DELETE $API/v1/meals/$M/components/$R3`                     | 200; 422 if it would drop below 2 components                 |
| 6 | reorder               | `POST $API/v1/meals/$M/components/reorder -d '{"recipe_ids":[$R2,$R1]}'` | 200; component order_index swapped                |
| 7 | favorite / unfavorite | `POST $API/v1/meals/$M/favorite` then `DELETE` same          | 201 then 200; `is_favorite` toggles inside `MealResponse`    |
| 8 | share                 | `POST $API/v1/meals/$M/share`                                | 201 first time (new token), 200 second (idempotent reuse)    |
| 9 | archive / restore     | `POST $API/v1/meals/$M/archive` then `POST .../restore`      | both 200; archived meal hidden from `GET /v1/meals` default  |

### MCP confirmation-gate paths

Two MCP tools require an explicit `confirm=true` for mutations — verify
the gate still trips after async conversion:

```python
# services/api/src/mcp_server/client.py
poetry run python services/api/src/mcp_server/client.py \
    --tool meal.remove_recipe_from_meal \
    --args '{"meal_id":"...","recipe_id":"..."}' \
    --base-url $API
# → expect: confirmation-required failure response (gate fires)

poetry run python services/api/src/mcp_server/client.py \
    --tool meal.remove_recipe_from_meal \
    --args '{"meal_id":"...","recipe_id":"...","confirm":true}' \
    --base-url $API
# → expect: 200, recipe removed

poetry run python services/api/src/mcp_server/client.py \
    --tool meal.archive_meal \
    --args '{"meal_id":"..."}' \
    --base-url $API
# → expect: confirmation-required

poetry run python services/api/src/mcp_server/client.py \
    --tool meal.archive_meal \
    --args '{"meal_id":"...","confirm":true}' \
    --base-url $API
# → expect: 200, meal archived
```

Paste the staging output here (truncated to ~50 lines per tool) before
closing the observation window.

---

## 4. Dual-Register Deviation + Cross-Domain Blast Radius

### 4.1 Dual-register deviation (aam-10 only)

aam-10 does **not** mount a `/_legacy_v1/meals` sibling router. Reason
(per AC 6 of the story):

- Single-user production traffic yields negligible differential signal
  from the extra 5-minute rollback window the dual-register pattern
  buys.
- Carrying ~500 LOC of snapshot-copied sync handler code through `aam-24`'s
  cleanup window is churn the epic avoided elsewhere.

**Rollback procedure**:

1. `git revert <aam-10-commit-sha>` on `main`.
2. `bin/prod-deploy` — ECS rolling deploy completes in ~10 min.
3. Verify in `bin/prod-script services/api/scripts/audit_errors.py --window 1h` that the spike subsides.
4. Verify in `bin/prod-script services/api/scripts/analyze_latency.py --window 1h` that the affected `normalized_path` p95 returns to the pre-aam-10 baseline.

**Last-good commit (pre-aam-10)**: `8109688` — `feat(api): aam-6 — async auth deps + race-test scaffolding`. Capture aam-10's own commit SHA after the squash-merge for the rollback runbook.

The runbook's dual-register pattern returns for subsequent domain
stories (aam-11 onwards) unless the user overrides per-story.

### 4.2 Cross-domain blast radius — non-meal source files touched

The story's File List intentionally scoped source changes to
`services/api/src/api/v1/meal/`, `libraries/utils/utils/services/meal_service.py`,
and `services/api/src/routers/v1/meal_router.py`. **Three additional
non-meal source files needed touching to keep cross-domain consumers
green** — flagging here so reviewers don't miss them:

| File                                                          | Change                                                                                                       | Why                                                                                                                                                                                                                                                                |
|---------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `services/api/src/api/v1/recipe/list_favorites.py`            | `Endpoint` → `AsyncEndpoint`; sync `db.query(...)` → `await db.execute(select(...))`; `await build_meal_summary(...)` | `_response.build_meal_summary` is now `async`. Calling it from a sync handler returned a coroutine that Pydantic rejected with `1 validation error for Response` — broke `/v1/favorites` for any user with a favorited Meal. Recipe domain stays sync otherwise.    |
| `services/api/src/api/v1/recipe/list_meals_using_recipe.py`   | Same conversion; `await self.database.find_by(Recipe, ...)` and `find_by(RecipeBookUser, ...)`.              | Same root cause as `list_favorites` — sync handler calling now-async `build_meal_summary` without `await`. Single recipe-domain endpoint converted; rest of recipe domain stays sync until aam-11.                                                                  |
| `services/api/src/routers/v1/recipe_router.py`                | The two routes above wired to `get_async_database` / `get_current_user_async`; `await ListFavorites.call(...)` and `await ListMealsUsingRecipe.call(...)`. | Required for the two converted handlers above. Other recipe routes left untouched.                                                                                                                                                                                  |
| `services/api/src/api/v1/meal_event/_meal_binding.py`         | `require_meal_available` — inlined sync `db.query(Meal).options(selectinload(...))` chain + sync `RecipeBookUser` membership check; removed `from api.v1.meal._access import require_meal_read`. | meal_event + recurrence_rule handlers stay sync (their domain story is later). They previously called sync `require_meal_read`; that helper is now async (AC 3). Inlining the sync version here keeps their handlers untouched and their tests green.            |

aam-10's File List should be amended to include these four files. The
spirit of the story is preserved — the blast-radius fixes are the
minimum-surface changes needed to honor AC 4 (async builders) without
breaking cross-domain consumers.

### 4.3 Test infrastructure changes

Two conftest changes were required for the converted tests to run:

- `services/api/tests/conftest.py:unauthed_client` — now also overrides
  `get_async_database` so the public-meal endpoint (`GET /v1/meals/public/{token}`,
  unauth'd + async) gets `MockAsyncDatabase` instead of crashing on a
  real `AsyncDatabase()` construction in the empty-`DATABASE_URL` test
  env.
- `services/api/tests/conftest.py` (module-level) — pre-warms
  `utils.services.units.normalize._cache_initialized = True` with empty
  sets. Sync mock-based tests previously got a no-op cache load via
  `MagicMock`; the async equivalent crashes at `mock_async_db.db.execute(...).scalars()`
  because the mock's `execute` is an `AsyncMock` returning a coroutine.
  Pre-warming side-steps `_ensure_cache` entirely. Tests that need
  canonical-unit translation must seed `_canonical_units` /
  `_alias_map` themselves.

### 4.4 Final test run (this batch only)

```text
poetry run pytest tests/test_share_meal.py tests/test_favorites_with_meals.py \
    tests/test_list_meals_filters.py tests/test_get_public_meal.py \
    tests/test_add_meal_to_shopping_list.py tests/test_list_meals_using_recipe.py \
    tests/test_rf2_response_shapes.py tests/test_meal_event_with_meals.py \
    tests/test_recurrence_rule_with_meals.py --no-cov -q

76 passed, 13 warnings in 5.34s
```

Per-file pass counts:

| File                                          | Tests passed |
|-----------------------------------------------|-------------:|
| `test_share_meal.py`                          |            7 |
| `test_favorites_with_meals.py`                |            3 |
| `test_list_meals_filters.py`                  |            9 |
| `test_get_public_meal.py`                     |            8 |
| `test_add_meal_to_shopping_list.py`           |            9 |
| `test_list_meals_using_recipe.py`             |            6 |
| `test_rf2_response_shapes.py`                 |            6 (full file; meal-section only is 2) |
| `test_meal_event_with_meals.py`               |           14 (passed unchanged after the `_meal_binding` fix) |
| `test_recurrence_rule_with_meals.py`          |           14 (passed unchanged after the `_meal_binding` fix) |
| **total**                                     |       **76** |

The sub-aam-10 batch A changes (test_meal_router.py, test_meal_components.py,
test_meal_service.py) are the parallel agent's responsibility — not
included in this run.
