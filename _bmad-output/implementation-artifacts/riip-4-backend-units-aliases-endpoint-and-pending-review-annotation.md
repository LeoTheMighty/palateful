# Story riip-4: Backend — `GET /v1/units/aliases` + pending_review_ingredient

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Two API additions for the Flutter side:
1. `GET /v1/units/aliases` returns the alias map + canonical token list,
   cached at the HTTP layer for 24 h. Powers the
   `SessionAliasMapProvider` so `UnitInput` can coerce on blur.
2. `GetImportItem` now annotates each ingredient on
   `parsed_recipe.ingredients[*]` with `pending_review_ingredient: true`
   when the linked canonical is pending or no match exists yet. Powers
   the Flutter ✨ badge.

## Scope (from epic)
- `services/api/src/api/v1/units/get_unit_aliases.py` — new
  `GetUnitAliases` Endpoint returns `{aliases, canonical}`.
- `services/api/src/routers/v1/units_router.py` — new router mounting
  `GET /units/aliases` under `/v1`. Sets
  `Cache-Control: max-age=86400, public` on the returned response and
  requires `get_current_user` (mirrors other `/v1/*` policy).
- `get_import_item.py` — new `_annotate_pending_review_ingredients`
  helper batches an `Ingredient.id IN (matched_ids)` query and emits
  `pending_review_ingredient: true` for ingredients whose canonical has
  `pending_review = true` OR whose `matched_ingredient_id` is null.
  Returns a NEW dict so the persisted `parsed_recipe` JSONB stays
  untouched.
- `list_import_items` is **not** modified — its response shape doesn't
  expose `parsed_recipe.ingredients`, so no annotation point exists.

## File List
- `services/api/src/api/v1/units/__init__.py` — new
- `services/api/src/api/v1/units/get_unit_aliases.py` — new
- `services/api/src/routers/v1/units_router.py` — new
- `services/api/src/routers/v1_router.py` — modified (mount new router)
- `services/api/src/api/v1/import_job/get_import_item.py` — modified
- `services/api/tests/test_units_endpoint.py` — new (4 tests)
- `services/api/tests/test_import.py` — modified (2 new tests for the
  annotation: matched + unmatched; empty-match-list path)

## Notes
- `Cache-Control` is set on the returned `CustomJSONResponse` directly
  (rather than via FastAPI's dependency-injected `Response`) because
  the Endpoint base class returns a Response object — FastAPI then
  ignores the dep-injected one.
- Matched-ID UUID parsing trusts the JSONB shape: `parsed_recipe` is
  internal data written by extract/match tasks, not user input. Defensive
  isinstance / try-except branches were removed at code-review time
  per project conventions ("Don't add error handling for scenarios that
  can't happen").
- `pending_review_ingredient: false` is **omitted** rather than emitted
  per the epic's open-question default — Flutter treats null == false,
  payloads stay smaller.

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-4-qa-walkthrough.md`.
