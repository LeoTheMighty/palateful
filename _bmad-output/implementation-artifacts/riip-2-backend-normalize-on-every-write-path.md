# Story riip-2: Backend — normalize on every write path

**Status:** done
**Epic:** epic-review-import-ingredient-polish

## Goal
Wire `normalize_unit_display` (riip-1) into every live path that
persists a unit: extract → match → approve → recipe CRUD → restore →
fork. Snapshots stay un-normalized to preserve history.

## Scope (from epic)
- `extract_recipe_task`:
  - `_serialize_recipe` normalizes each ingredient `unit` before the
    `parsed_recipe` JSONB is written.
  - `_parse_raw_ingredients` (spreadsheet path) normalizes each
    `ing["unit"]` before adding to the result list.
- `create_recipe_task._create_recipe_ingredient`: normalizes
  `ing_data["unit"]` before persisting `RecipeIngredient.unit_display`.
- `update_import_item`: new `_normalize_user_edits_units` helper walks
  `params.user_edits["ingredients"][*]["unit"]` and coerces each
  before persist. Operates on a copy so callers' input dicts aren't
  mutated.
- `create_recipe` / `update_recipe` API endpoints: normalize each
  `ing_input.unit` before constructing the `RecipeIngredient` row.
- `restore_recipe_version`: normalizes the snapshot's `unit_display`
  before writing the new live row (snapshots are still preserved
  un-normalized; design principle 5).
- `fork_recipe`: normalizes `ing.unit_display` when cloning into the
  new recipe (design principle 7).
- `_create_version_snapshot` in `update_recipe.py` is **not** wired —
  enforced by `test_snapshot_path_does_not_import_normalize_unit_display`
  which greps the function body for the call.

## File List
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` — modified
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` — modified
- `services/api/src/api/v1/import_job/update_import_item.py` — modified (+ helper)
- `services/api/src/api/v1/recipe/create_recipe.py` — modified
- `services/api/src/api/v1/recipe/update_recipe.py` — modified
- `services/api/src/api/v1/recipe/restore_recipe_version.py` — modified
- `services/api/src/api/v1/recipe/fork_recipe.py` — modified
- `services/api/tests/test_import.py` — modified (new
  `test_update_import_item_normalizes_ingredient_units` covers the helper +
  raises coverage to 100%)
- `libraries/utils/test/test_unit_normalize_write_paths.py` — new
  (parametrized round-trip covering serialize/raw/create paths +
  snapshot-exclusion guard)

## Notes
- Each callsite passes a `context={"path": "<callsite>"}` dict so audit
  rows in `error_logs` can be grouped/grepped by path when we harvest
  the alias seed in a future story.
- Wizard draft save endpoint audit: there is no separate wizard-draft
  endpoint today — the wizard flow goes through `create_recipe` (and
  later `update_recipe`), both of which now normalize. So AC5 is a
  no-op for v1; if a draft endpoint is added later it must adopt the
  same pattern.
- `match_ingredients_task` is intentionally NOT touched — it operates
  on names, not units, per the epic.

## QA walkthrough
See `_bmad-output/implementation-artifacts/riip-2-qa-walkthrough.md`.
