# QA Walkthrough — str-ing-3 (Backend: delete /v1/ingredients/* endpoints + router)

**Epic:** epic-ingredients-string-simplification
**Scope:** backend-only — net deletion. Ship alongside str-ing-2 so the full "no matching" thesis lands in one prod deploy.

## Pre-flight
- [ ] `git log --oneline origin/main..HEAD` shows the `feat(backend): str-ing-3 — delete /v1/ingredients/* endpoints + router` commit.
- [ ] `npx nx run api:test` passes with **2025 tests green** and coverage at **100.00%**.
- [ ] `npx nx run api:lint` passes.
- [ ] `ls services/api/src/api/v1/ingredient/` → "No such file or directory".
- [ ] `ls services/api/tests/test_ingredient.py` → "No such file or directory".
- [ ] `ls services/api/src/routers/v1/ingredient_router.py` → "No such file or directory".
- [ ] `rg '/v1/ingredients' services/ app/ docs/` returns zero hits in `services/` and `app/`; only `_bmad-output/**` / `docs/**` planning-artifact hits.

## Smoke — endpoints gone
1. Start the stack: `docker compose up`.
2. `curl -i http://localhost:8000/v1/ingredients/search?q=sugar` → **404 Not Found**.
3. `curl -iX POST http://localhost:8000/v1/ingredients -H 'content-type: application/json' -d '{"canonical_name":"sugar"}'` → **404 Not Found**.
4. `curl -i http://localhost:8000/v1/ingredients/abc-123` → **404 Not Found**.
5. Unrelated endpoints still respond (e.g. `GET /v1/health` → 200).

## Smoke — MCP tool inventory
1. With the stack up, query the MCP endpoint's tool list (via an authenticated MCP client or the test harness).
2. Confirm `unified_search` is present, `search_ingredients` is absent.
3. Tool count totals 27 (was 28).

## Regression guard
- [ ] Recipe creation still works (Flutter + MCP) — ingredient rows are staged inline inside the create/update endpoints from str-ing-2.
- [ ] Pantry add / remove still works with both `ingredient_id` and `name` payloads.
- [ ] Shopping list populate / add-meal endpoints still pass through `aggregate_meal_ingredients` in no-dedup mode.
- [ ] `POST /v1/import-jobs` and recipe-import happy path still surface as usual in the Activity Hub.

## Hand-off to str-ing-4
- Safe to drop `ingredients.embedding`, `ingredients.parent_id`, `ingredients.pending_review`, `ingredients.is_canonical`, `ingredients.aliases`, `ingredients.category`, unique index, pg_trgm GIN, HNSW, and `search_ingredients_fuzzy` PL/pgSQL — no runtime reader remains.
- Data-loss caveat on down-migration (restoring columns-as-empty) still applies; dogfood regime accepts.
