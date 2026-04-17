# Story bugs-imp-ing-5: Backend name-or-id input on recipe create/update

Status: done

## Story

As the recipe-create and recipe-update endpoints,
I want to accept either an `ingredient_id` (existing canonical) or a `name`
(find-or-create),
so that the wizard and edit-screen can send the same structured shape the
import path already supports.

## Context

Today `CreateRecipe.IngredientInput` / `UpdateRecipe.IngredientInput` hard
require `ingredient_id: str`. The recipe wizard's in-memory shape is
nothing like that; the edit screen currently has no ingredient editor at
all. Story 4 depends on this endpoint change before it can ship.

The find-or-create logic already lived inside
`CreateRecipeTask._create_recipe_ingredient` in the import worker. This
story extracts it into a single shared helper so the endpoint and worker
resolve ingredients identically going forward.

## Acceptance Criteria — all green

1. New `libraries/utils/utils/services/ingredient_resolver.py` with
   `resolve_ingredient(database, *, ingredient_id, name, submitted_by_id)`.
2. `create_recipe.py` and `update_recipe.py` accept either
   `ingredient_id` or `name`. When both are present, `ingredient_id`
   wins. When neither is present, returns 400 with the new
   `ErrorCode.INGREDIENT_INPUT_REQUIRED` (= 123).
3. Unknown `ingredient_id` continues to 400 with
   `ErrorCode.INGREDIENT_NOT_FOUND` — no behavior change for existing
   clients.
4. `name` flow lowercases + strips + `find_or_create_by` on
   `canonical_name` with `pending_review=True, submitted_by_id=user.id`.
5. `CreateRecipeTask._create_recipe_ingredient` refactored to call the
   same helper — one place to evolve the rule.
6. 10-test pytest suite in `services/api/tests/test_recipe_ingredient_input.py`
   covering create + update with name-only, id-only, both, neither,
   blank name, normalization, unknown id, and name-reuse paths.

## Key Files

- Create: `libraries/utils/utils/services/ingredient_resolver.py`
- Modify: `services/api/src/api/v1/recipe/create_recipe.py`
- Modify: `services/api/src/api/v1/recipe/update_recipe.py`
- Modify: `services/api/src/schemas/recipe.py` (unused schema,
  kept in sync with the inline endpoint models for consistency)
- Modify: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
- Modify: `libraries/utils/utils/classes/error_code.py` (new `INGREDIENT_INPUT_REQUIRED = 123`)
- Test: `services/api/tests/test_recipe_ingredient_input.py`
