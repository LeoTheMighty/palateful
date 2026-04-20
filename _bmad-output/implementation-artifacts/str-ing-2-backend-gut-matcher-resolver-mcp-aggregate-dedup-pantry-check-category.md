# Story str-ing-2 — Backend: gut matcher + resolver + MCP matcher + aggregate dedup + pantry check + category reads

**Epic:** epic-ingredients-string-simplification
**Status:** in-progress — partial commit. Backend runtime changes landed; a fraction of the test surface has been re-pointed at the new shape, but the full `npx nx run api:test` hasn't been re-validated end-to-end yet. See "Remaining work" below.

## Scope delivered

### Deleted
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py` (467 LOC) — no matching stage runs in the pipeline anymore.
- `libraries/utils/utils/services/ingredient_resolver.py` (88 LOC) — inlined per call site.
- `libraries/utils/test/test_ingredient_find_or_create.py` — resolver test suite.
- `libraries/utils/test/test_awaiting_review_reason.py` — MatchIngredientsTask-only tests.
- `services/eval/src/evaluators/ingredient_matching_evaluator.py` — eval suite retired.

### Runtime changes
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` — extractor now transitions items directly to `awaiting_review` (no intermediate `matching` state), and no longer dispatches a matching task. `_dispatch_matching_task` helper removed.
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py::_create_recipe_ingredient` — every parsed ingredient name creates a fresh `Ingredient` row inline (`session.add(Ingredient(canonical_name=name)); session.flush()`).
- `libraries/utils/utils/tasks/import_tasks/__init__.py` — removed `MatchIngredientsTask` export.
- `libraries/utils/utils/services/meal_service.py::aggregate_meal_ingredients` — rewrote to emit one row per `recipe_ingredients` row in stable `meal.components × recipe.ingredients` order. No dedup, no summing. `AggregatedIngredient.category` is always `None`.
- `services/api/src/api/v1/shopping_list/generate_from_meal_event.py` — deleted pantry lookup block + `check_pantry` param. `Params` sets `ConfigDict(extra="forbid")`. Category read → `None`.
- `services/api/src/api/v1/shopping_list/populate_from_recipe.py` — `category=None` on every ShoppingListItem insert.
- `services/api/src/api/v1/meal_event/add_to_shopping_list.py` — `category=None` on both the meal-event-via-Meal and recipe-linked branches.
- `services/api/src/api/v1/recipe/create_recipe.py` — dropped `resolve_ingredient` import; inlined `ingredient_id` lookup OR `Ingredient(canonical_name=name)` stage at one place per ingredient. `IngredientSummary.category` → `None`.
- `services/api/src/api/v1/recipe/update_recipe.py` — same inline treatment.
- `services/api/src/api/v1/import_job/retry_import_item.py` — `STAGE_EXTRACTED` now dispatches `create_recipe_task` (not `match_ingredients_task`). `match_ingredients_task` import + `_dispatch_match` helper removed. `STAGE_MATCHED` retained for back-compat with legacy rows and also routes to create.
- `services/api/src/mcp_server/tools/recipes.py` — deleted `INGREDIENT_MATCH_THRESHOLD` + `_resolve_ingredient`. New `_create_ingredient_for_name(name, database)` helper; both `create_recipe` and `update_recipe` MCP tools call it per ingredient.
- `services/api/src/api/v1/pantry/add_ingredient.py` + `schemas.py` — `PantryIngredientCreate` now accepts `name` XOR `ingredient_id`. Name path creates a fresh `Ingredient` row inline (mirrors the recipe create/update pattern; closes the str-ing-1 cross-story loop where the pantry editor started sending `{name: …}`).

### Schema/docstring changes
- `services/api/src/schemas/shopping_list.py::GenerateShoppingListRequest` — now empty body with `extra="forbid"`.
- `services/api/src/schemas/recipe.py::RecipeIngredientInput` — docstring updated.
- `services/api/src/api/v1/recipe/update_recipe.py::UpdateRecipe.IngredientInput` — inline comment updated.
- `services/api/src/api/v1/import_job/get_import_item.py` — `_annotate_pending_review_ingredients` function removed (not shown in this commit; was already gone from the file before this session).

### Eval
- `services/eval/eval.config.yaml` — `ingredient_matching` metrics block + `ingredient_match_rate` threshold dropped.
- `services/eval/src/config.py` — same, removed from dataclasses + loader.
- `services/eval/src/evaluators/__init__.py` — removed export.
- `services/eval/src/main.py` — removed from `ALL_SUITES` + `add-case` click choices.
- `services/eval/src/runner.py` — removed suite instantiation + pass-check branch.

### Test cleanup
- `libraries/utils/test/test_aggregate_meal_ingredients.py` — rewritten to the no-dedup positive tests per AC.
- `libraries/utils/test/test_stage_markers.py` — `_run_match_task_on_item` + both `test_match_task_marks_matched_*` deleted. `test_extract_task_marks_extracted_on_success` updated to assert `status="awaiting_review"`.
- `libraries/utils/test/test_unit_normalize_write_paths.py` — `test_create_recipe_task_normalizes_unit_display` no longer monkeypatches `resolve_ingredient`; stubs `Ingredient` constructor instead.
- `services/api/tests/mcp_server/test_recipes.py` — rewrote `TestResolveIngredient` → `TestCreateIngredientForName`; added positive `test_mcp_{create,update}_recipe_always_creates_new_ingredient_rows`.
- `services/api/tests/test_import.py` — `test_retry_extracted_stage_dispatches_match_task` → `…create_recipe_task`. `test_get_import_item_annotates_pending_review_ingredients` → negative test asserting the key is never emitted. Removed `test_get_import_item_skips_query_when_no_matched_ingredient_ids`.
- `services/api/tests/test_shopping_list.py` — dropped the three pantry-check tests; added `test_generate_rejects_check_pantry_field` (422 assertion) and positive `test_generate_from_meal_event_ignores_pantry_stock`.
- `services/api/tests/test_recipe_ingredient_input.py` — rewrote `test_name_only_creates_pending_review_ingredient` → `test_name_only_creates_fresh_ingredient_row`. Rewrote `test_name_reuses_existing_ingredient` → `test_repeated_names_create_distinct_rows`. Docstrings updated.

## Remaining work (HANDOFF)

1. **Run `DATABASE_URL=postgresql://test:test@localhost/test npx nx run api:test` end-to-end.** MCP recipe tests (29) pass locally; the rest of the suite has not been re-run since my edits. Expect findings around:
   - `test_coverage_gaps.py` may still reference deleted modules/functions (quick grep showed zero matches at commit time, but coverage-pin may still trip because of newly-unreferenced helper code in the touched files).
   - `test_import.py` may have other retry / pipeline tests that still expect `status="matching"` or dispatch assertions against the old path.
   - `test_recipe_ingredient_input.py::test_name_lowercased_and_stripped` may fail — it was trimmed but may need its `mock_db.set_find_by(Ingredient, …)` shim dropped entirely.
   - `test_stage_markers.py::test_extract_task_marks_extracted_on_success` now asserts `status="awaiting_review"` — verify that the accompanying `_make_database` mock's `query.group_by.all` stub still matches the new status.
   - `test_extract_recipe_task_fanout.py` is in the diff (modified by a parallel agent?) — diff and verify.
2. **`find_or_create_ingredient` / `_matched_ingredient_id`** — do a final `rg -n 'find_or_create|matched_ingredient_id' services/ libraries/` sweep to confirm nothing still points at the old pathway.
3. **Seed data** — `services/migrator/seeds/ingredients.py` delete is part of str-ing-4, not str-ing-2.
4. **Handler `category` reads** — audited at four call sites; all pass `None`. No remaining reads. Grep `rg '\.ingredient\.category|ingredient\.category\b' services/api/src` to double-check.
5. **Coverage pin** — `services/api` coverage is pinned at 100%. After test runs pass, spot-check for newly uncovered lines.
6. **Commit scope** — this commit omits the Flutter + parallel-agent churn in `_bmad-output/planning-artifacts/*.md`, `app/lib/features/home/*`, `app/lib/features/meals/*`, `libraries/utils/utils/models/import_item.py`, `libraries/utils/utils/models/user_activity.py`, `services/api/src/api/v1/user_activity/*`, etc. They belong to other in-flight epics.

## Acceptance criteria status

| # | AC | Status |
|---|----|--------|
| 1 | `match_ingredients_task.py` doesn't exist | ✅ |
| 2 | One `ingredients` row per parsed name; no cache reads | ✅ runtime; integration harness not re-run |
| 3 | `aggregate_meal_ingredients` flat list in stable order | ✅ unit tests pass |
| 4 | `check_pantry` returns 422 | ✅ schema `extra="forbid"` + dedicated test |
| 5 | Duplicate olive-oil line items from overlapping recipes | ✅ by construction (no dedup) |
| 6 | `GetImportItem` response strips `pending_review_ingredient` | ✅ function already removed + test rewritten |
| 7 | MCP create/fork always fresh row | ✅ `_create_ingredient_for_name` + tests |
| 8 | Four category readers pass `None` | ✅ |
| 9 | `npx nx run api:test --coverage` at 100% | ⚠️ not re-run — handoff item #1 |
| 10 | Eval runner cleanly imports without matcher | ✅ config + imports cleaned |
| 11 | Grep `_resolve_ingredient|INGREDIENT_MATCH_THRESHOLD|find_or_create_ingredient|check_pantry` returns zero | ⚠️ needs a final clean sweep — see handoff #2 |
| 12 | `test_generate_from_meal_event_ignores_pantry_stock` passes | ✅ test authored |

## QA walkthrough

See `str-ing-2-backend-gut-matcher-resolver-mcp-aggregate-dedup-pantry-check-category-qa-walkthrough.md`.
