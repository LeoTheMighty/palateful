# Story 13.3: Fix Pipeline Gaps

## Summary

Closed gaps in the recipe import pipeline where ingredients without matches were being dropped, causing incomplete recipe imports.

## Changes

### 1. Auto-create ingredients when no match (`match_ingredients_task.py`)

- **Before**: When no ingredient match was found (tier 4), the task returned `ingredient_id: None`, `confidence: 0`, `match_type: "none"`, `needs_review: True`. This caused downstream issues since the ingredient had no ID.
- **After**: When no match is found, a new `Ingredient` record is created with `pending_review=True`, `is_canonical=False`, and `submitted_by_id` set to the importing user. The match result returns the new ingredient's ID with `confidence: 0.5`, `match_type: "auto_created"`, `needs_review: False`.

### 2. Don't drop unmatched ingredients in `create_recipe_task.py`

- **Before**: `_create_recipe_ingredient` skipped any ingredient without a `matched_ingredient_id`, logging a warning and returning early. This meant unmatched ingredients were silently dropped from the recipe.
- **After**: If `matched_ingredient_id` is still `None` (safety net), the task creates the ingredient inline with `pending_review=True` instead of skipping it. All ingredients are now preserved in the final recipe.

### 3. Auto-approve high-confidence extractions including auto-created

- **Before**: The auto-approve logic already worked for high-confidence matches, but unmatched ingredients always set `needs_review=True`, forcing manual review even when the ingredient name was clear.
- **After**: Auto-created ingredients return `needs_review: False`, so recipes where all ingredients are either high-confidence matches or auto-created will be auto-approved and dispatched to `create_recipe_task` without manual review. Updated comments to clarify this behavior.

## Files Modified

- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py`
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
