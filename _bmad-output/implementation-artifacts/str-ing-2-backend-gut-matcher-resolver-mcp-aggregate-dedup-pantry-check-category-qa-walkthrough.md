# QA Walkthrough — str-ing-2 (Backend: gut matcher/resolver/MCP/aggregate-dedup/pantry-check/category)

**Epic:** epic-ingredients-string-simplification
**Scope:** backend-only — no Flutter rebuild required. Ship alongside str-ing-1's Flutter commit.

## Pre-flight
- [ ] `git log --oneline origin/main..HEAD` shows the `feat(backend): str-ing-2 — retire ingredient matcher…` commit plus the `feat(backend): str-ing-2 — finish tests + pantry name-input coverage` follow-up.
- [ ] `npx nx run api:test` passes with **2035 tests green** and coverage at **100.00%**.
- [ ] `npx nx run api:lint` passes.
- [ ] `npx nx run utils:test` passes with **273 tests green**.
- [ ] `npx nx run utils:lint` passes.
- [ ] `rg '_resolve_ingredient|INGREDIENT_MATCH_THRESHOLD|find_or_create_ingredient|_annotate_pending_review_ingredients|ingredient_matching_evaluator' services/ libraries/` returns zero matches in source (all runtime code paths gone).

## Smoke — import pipeline (manual)
1. Start the stack: `docker compose up`.
2. Import a URL recipe that uses "olive oil" in two ingredient rows.
3. Confirm two distinct `ingredients` rows land (`SELECT id, canonical_name FROM ingredients WHERE canonical_name = 'olive oil' ORDER BY created_at DESC LIMIT 4`) — no dedup.
4. Confirm no row ends up with `status='matching'`; every item transitions `extracted → awaiting_review` in a single step.
5. Confirm `ingredient_matches` table stays at row count 0 after the import (cache write path gone).

## Smoke — shopping list duplicate behaviour
1. Create a Meal with two recipes that both list olive oil.
2. `POST /v1/meals/{meal_id}/add-to-shopping-list`.
3. Confirm two adjacent "olive oil" rows on the shopping list, in `meal.components × recipe.ingredients` order, each with its own per-recipe quantity.
4. Re-tap Add-to-Shopping-List — confirm `items_added=0, items_skipped=2` (existing `(ingredient_id, source_meal_id)` key dedups both new rows).

## Smoke — pantry check gone
1. Add olive oil to the pantry for the logged-in user.
2. Plan a meal that needs olive oil.
3. `POST /v1/shopping-lists/{id}/populate-from-meal-event` (or the per-meal-event path).
4. Confirm the olive oil line item **still appears** on the list — the pantry-stock-aware branch is deleted, not toggled off.
5. `POST /v1/shopping-lists/{id}/populate-from-meal-event` with `{"check_pantry": true}` in the body → confirm **422** (Pydantic `extra="forbid"` rejects the unknown field).

## Smoke — MCP parity
1. Trigger the MCP `create_recipe` tool with an olive-oil ingredient and a second recipe via `fork_recipe` with the same name.
2. Confirm the MCP path creates a fresh `ingredients` row per ingredient name (not a shared row via `_resolve_ingredient`).
3. Verify `rg 'INGREDIENT_MATCH_THRESHOLD|_resolve_ingredient' services/api/src/mcp_server/` is empty.

## Smoke — import response shape
1. `GET /v1/import-jobs/{id}/items/{item_id}` on any parsed import.
2. Confirm no ingredient in the response carries a `pending_review_ingredient` key (the annotator is deleted).

## Regression guard
- [ ] Recipe CRUD still accepts both `ingredient_id` and `name` per-ingredient (back-compat for clients that send IDs).
- [ ] `shopping_list_items.category` ends up NULL for new rows post-deploy — four handlers pass `category=None`.
- [ ] `aggregate_meal_ingredients` still returns an `AggregatedIngredient` list with stable order, just one row per `recipe_ingredients` row (no summing).
- [ ] `ExtractRecipeTask` fan-out still emits `awaiting_review` for both the original item and any siblings.
- [ ] `STAGE_EXTRACTED` and the legacy `STAGE_MATCHED` retry dispatch paths both route to `create_recipe_task` now.

## Known caveats to flag if observed
- Existing prod `ingredients` rows with raw-string `canonical_name` values stay as-is — no data migration. Shopping lists from old meals may show ugly line items.
- Duplicate line items on overlapping-recipe meals are **expected**, not a regression.
- `shopping_list_items.already_have_quantity` column is retained but will be NULL on every new write (kept as placeholder per design).

## Hand-off to str-ing-3
- Flutter already stopped calling `/v1/ingredients/*` in str-ing-1.
- Backend runtime now passes through to endpoint deletion in str-ing-3.
- Schema migration (str-ing-4) depends on this landing first so handlers stop reading dropped columns.
