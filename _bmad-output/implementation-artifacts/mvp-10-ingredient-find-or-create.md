# Story MVP.10: Ingredient Find-or-Create (Unique Constraint Fix)

Status: done

## Story

As a user importing recipes,
I want ingredients to be safely deduplicated during parallel imports,
so that my imports don't fail with a database constraint error when two recipes share the same ingredient.

## Context

Production error: `UniqueViolation: duplicate key value violates unique constraint "ingredients_canonical_name_key"`. When the import pipeline fans out `MatchIngredientsTask` in parallel (one per recipe), two tasks can both see "no match" for the same ingredient (e.g. "salt"), both reach Tier 4 (auto-create), and both try to INSERT — the second one hits the unique constraint and fails.

The fix is surgical: `Database.find_or_create_by()` already exists at `libraries/utils/utils/services/database.py:81` with advisory locking. It's just not being used in the two ingredient-creation call sites.

### Root Cause

Two call sites create `Ingredient` records via raw `database.create()` with no dedup check:
1. `match_ingredients_task.py:213-219` — Tier 4 auto-create when no match found
2. `create_recipe_task.py:138-144` — Safety-net fallback for unmatched ingredients

### Why Advisory Lock Is Sufficient

All Celery workers share the same PostgreSQL instance. `find_or_create_by` acquires a pg advisory lock keyed on `Ingredient_canonical_name_{name}`, serializing concurrent creates for the same ingredient name. The second caller finds the row the first caller just created and returns it.

## Acceptance Criteria

1. `MatchIngredientsTask._match_ingredient` Tier 4 uses `database.find_or_create_by(Ingredient, ...)` instead of raw `Ingredient()` + `database.create()`.
2. `CreateRecipeTask._create_recipe_ingredient` safety-net path uses `database.find_or_create_by(Ingredient, ...)` instead of raw `Ingredient()` + `database.create()`.
3. When `find_or_create_by` returns an existing ingredient (created by a concurrent task), the returned ingredient is used — no error raised, no duplicate created.
4. The `canonical_name` passed to `find_or_create_by` is normalized (lowercased, stripped) to match the existing Tier 2 exact-match behavior.
5. Both call sites set `defaults` for `is_canonical=False`, `pending_review=True`, `submitted_by_id=user_id` — these are only applied on create, not on find.
6. Existing Tier 1-3 matching behavior is unchanged — only Tier 4 and the safety-net fallback are modified.
7. All existing import tests continue to pass.
8. New test: two concurrent calls to `_match_ingredient` with the same ingredient text both succeed and return the same `ingredient_id`.

## Tasks / Subtasks

- [ ] Task 1: Fix `MatchIngredientsTask` Tier 4 (AC: #1, #3, #4, #5)
  - [ ] In `_match_ingredient`, replace lines 213-219 with `database.find_or_create_by(Ingredient, defaults={...}, canonical_name=ingredient_name)`
  - [ ] Ensure `ingredient_name` is already lowered/stripped (it is — `_extract_ingredient_name` receives `normalized` which is `ingredient_text.lower().strip()`)
  - [ ] Verify the returned ingredient's `id` is used for the cache and return dict

- [ ] Task 2: Fix `CreateRecipeTask` safety-net (AC: #2, #3, #4, #5)
  - [ ] In `_create_recipe_ingredient`, replace lines 138-144 with `database.find_or_create_by(Ingredient, defaults={...}, canonical_name=ingredient_name)`
  - [ ] Normalize `ingredient_name` (lowercase + strip) before passing — the current code uses raw `ing_data.get("text")` which may not be normalized

- [ ] Task 3: Tests (AC: #6, #7, #8)
  - [ ] Add test verifying `find_or_create_by` is called (not `create`) for Tier 4 auto-creation
  - [ ] Add test verifying the safety-net path in `create_recipe_task` uses `find_or_create_by`
  - [ ] Add test simulating concurrent ingredient creation: two calls with same canonical_name, assert both return the same ingredient ID and no exception raised
  - [ ] Run full test suite to verify no regressions

## Dev Notes

- **Zero-migration fix**: `find_or_create_by` is an application-level change only. No new columns, no schema changes.
- **Advisory lock key format**: `find_or_create_by` builds the lock key as `Ingredient_canonical_name_{value}`. This serializes on the exact `canonical_name` value, so different ingredients are not blocked.
- **`_extract_ingredient_name` normalization**: This function strips quantities, units, parentheticals, and post-comma text. It's deterministic for the same input but may produce different results for semantically similar inputs ("garlic cloves" vs "cloves garlic"). That's a separate matching-quality issue, not a constraint-violation issue — out of scope for this story.
- **`create_recipe_task` normalization gap**: The safety-net path currently uses `ing_data.get("text")` without lowercasing. This must be normalized before passing to `find_or_create_by` to match the convention.

### References

- `libraries/utils/utils/services/database.py:81` — `find_or_create_by` with advisory lock
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py:211-228` — Tier 4 auto-create
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py:134-145` — Safety-net fallback
- `libraries/utils/utils/models/ingredient.py:31` — `canonical_name` unique constraint
- [Epic: epic-mvp-finalization.md]
