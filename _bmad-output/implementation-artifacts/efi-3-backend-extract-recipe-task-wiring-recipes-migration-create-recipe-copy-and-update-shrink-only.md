# Story efi-3 — extract_recipe_task wiring + `recipes.inferred_fields` migration + `create_recipe_task` copy + `GetRecipe` / `UpdateRecipe` surface with shrink-only

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** efi-1 (guardrails / penalty / log helper), efi-2 (ExtractedRecipe.inferred_fields + parsers)

## Scope

Flow `inferred_fields` end-to-end through persistence:

1. `extract_recipe_task` applies `apply_guardrails` + `apply_inference_penalty` on the extractor output, then `_serialize_recipe` writes the cleaned list under `parsed_recipe.inferred_fields`.
2. Alembic migration adds `recipes.inferred_fields` (JSONB NOT NULL DEFAULT `'[]'::jsonb`). SQLAlchemy model declares the column.
3. `create_recipe_task` copies `parsed_recipe.inferred_fields` onto the new Recipe via a helper that defense-in-depth filters to `INFERABLE_FIELDS` and dedupes.
4. `GetRecipe` surfaces `inferred_fields` at the response root.
5. `UpdateRecipe` accepts `inferred_fields` with strict shrink-only validation — client can only remove names already on the stored list. Expansion → 400 with the current stored set in `data.allowed`.

## Implementation notes

- Extractor already resolves confidence inside `_parse_ai_response` (irrd-3 design). We apply guardrails + inference penalty in a module-level helper `_apply_inference_post_processing` invoked BEFORE `_serialize_recipe`. Order matters because guardrails can DROP a vibe → `inferred_count` shrinks → penalty shrinks too.
- Sibling fan-out recipes get guardrails with `import_item_id=None` because the sibling `ImportItem` rows don't exist yet; the audit row's `import_item_id` column is already nullable.
- `_serialize_recipe` writes `"inferred_fields": list(recipe.inferred_fields)` — defensive copy so downstream mutations to the recipe object can't leak into stored JSONB.
- `_filter_inferred_fields` is a standalone helper (not inlined) so the allow-list / dedupe rule has one test entry point.
- `UpdateRecipe` uses `return failure(status=400, ...)` instead of `raise APIException(...)` because the error response needs structured `data.allowed` — `APIException.detail` is a string.
- Migration revision ID `efi3infrfields1` chains off `abi2bsoftarch1`. Filename timestamp `20260420030000_` chosen to sort after `abi-2b` (20260420010000_) and the parallel-agent WIP at `20260420020000_*` so the ordering is clean regardless of which lands first.

## File list

- `services/migrator/migrations/versions/20260420030000_add_inferred_fields_to_recipes.py` [NEW] — JSONB column with `'[]'::jsonb` default.
- `libraries/utils/utils/models/recipe.py` [MODIFY] — `inferred_fields: Mapped[list[str]]` JSONB column.
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` [MODIFY] — `_apply_inference_post_processing` helper + wiring in `_update_item_from_result`; `_serialize_recipe` persists `inferred_fields`.
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` [MODIFY] — `_filter_inferred_fields` helper; `Recipe.inferred_fields` populated on creation.
- `services/api/src/api/v1/recipe/get_recipe.py` [MODIFY] — surface `inferred_fields` at response root.
- `services/api/src/api/v1/recipe/update_recipe.py` [MODIFY] — accept `inferred_fields` with subset-of-allow-list + subset-of-stored validation; return 400 + `data.allowed` on violation.
- `services/api/tests/conftest.py` [MODIFY] — `MockRecipe` default `inferred_fields=[]`.
- `libraries/utils/test/test_extract_recipe_task_inference.py` [NEW] — 6 tests (helper + 4 integration paths).
- `libraries/utils/test/test_create_recipe_task_inferred_fields.py` [NEW] — 6 tests covering the filter helper.
- `services/api/tests/test_recipe.py` [MODIFY] — `TestRecipeInferredFields` class with 9 tests covering GetRecipe + UpdateRecipe surfaces + shrink-only validation paths.

## Acceptance criteria — coverage

| AC | How |
|----|-----|
| 1 | `_apply_inference_post_processing` in extract_recipe_task; covered by `test_post_processing_applies_guardrails_and_penalty` + `test_update_item_persists_inferred_fields_in_parsed_recipe`. |
| 2 | `20260420030000_add_inferred_fields_to_recipes.py` — `op.add_column` with JSONB NOT NULL DEFAULT `'[]'::jsonb`; `op.drop_column` in downgrade. |
| 3 | `libraries/utils/utils/models/recipe.py` — `Mapped[list[str]]` on JSONB. |
| 4 | `create_recipe_task.py` — `Recipe(..., inferred_fields=_filter_inferred_fields(recipe_data.get("inferred_fields")))`; filter covered by `test_create_recipe_task_inferred_fields.py` (6 tests). |
| 5 | `get_recipe.py` — `inferred_fields=list(recipe.inferred_fields or [])`; covered by `TestRecipeInferredFields::test_get_recipe_*`. |
| 6 | `update_recipe.py` — subset-of-allow-list + subset-of-stored + 400 response with `data.allowed`; covered by `TestRecipeInferredFields::test_update_recipe_rejects_expansion` / `test_update_recipe_rejects_non_inferable_field`. |
| 7 | `test_update_item_persists_inferred_fields_in_parsed_recipe` — verifies guardrails + penalty interact with persistence. |
| 8 | `TestRecipeInferredFields::test_get_recipe_surfaces_inferred_fields`. |
| 9 | `TestRecipeInferredFields::test_update_recipe_shrinks_inferred_fields` + `test_update_recipe_rejects_expansion`. |
| 10 | All new branches covered by the test classes above. |
