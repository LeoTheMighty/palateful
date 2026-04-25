# recipe-list-org-2 — QA Walkthrough

**Story:** Backend hide-in-meals filter (server or client decision)
**Epic:** `epic-recipe-list-organization`
**Status:** review

## Audit verdict

Already documented in the story body — server still does the work
because the book-detail screen would otherwise have to over-fetch
meals. The filtering itself stays client-side (no `?hide_in_meals=true`
query param), but the fields the client filters on (`is_in_meal`,
`total_in_meals`) now ride on the recipe-list payloads.

## Smoke

| # | Step | Expected |
|---|------|----------|
| 1 | `GET /v1/recipe-books/{book_id}/recipes` against a book where one recipe is in a non-archived meal | 200; that recipe's `is_in_meal: true`; other recipes' `is_in_meal: false`; `total_in_meals: 1` |
| 2 | Add a second recipe in the same book to a meal; re-issue the call | `total_in_meals: 2`; both rows `is_in_meal: true` |
| 3 | Archive one of the meals (`UPDATE meals SET archived_at = now() WHERE id = ...`); re-issue | The recipe whose only meal is archived flips back to `is_in_meal: false`; `total_in_meals` decrements |
| 4 | `GET /v1/recipe-books/{book_id}` (book detail) | 200; embedded `recipes[].is_in_meal` populated; `total_in_meals` at top level matches the sum of `is_in_meal` flags |

## Edge cases

| # | Step | Expected |
|---|------|----------|
| E1 | A recipe is referenced by **two** non-archived meals | `is_in_meal: true`, but `total_in_meals` only counts the recipe once (DISTINCT in the count query) |
| E2 | Empty book (no recipes) | `total_in_meals: 0`; per-page meal lookup short-circuits on empty page |
| E3 | A `meal_recipes` row whose `archived_at` is set, parent meal active | `is_in_meal: false` (we filter both join-row + parent-meal archive) |
| E4 | Recipe in this book referenced by a meal in **another** book | `is_in_meal: true` (a meal in any book hides the recipe — the user-mental-model is "this recipe is curated into a meal somewhere") |
| E5 | `?search=...` with hits | Search filter doesn't change `total_in_meals` — that count is the **whole-book** total, not the search-match total. Client surface assumes this. |

## Performance

Same gate as story 1 — capture baseline before push, verify post-deploy
that p95 of both endpoints does not regress > 50ms.

The new aggregates use `ix_meal_recipes_recipe_id` (already exists per
the model file) for the per-page lookup and the count. No new index.

## Regression

| # | Step | Expected |
|---|------|----------|
| R1 | sort=last_cooked still works | unchanged |
| R2 | Existing favorite + tag fields still serialize | unchanged |
| R3 | total_in_meals defaults to 0 on responses where all recipes are loose | matches both shapes |

## Known parallel-session note

Same as story 1: a concurrent `epic-recipe-bulk-organize` Story 2 is in
flight in the same working tree, mutating `bulk_move_recipes.py` to add
a `moved` field. CI on a clean checkout will only see what each story
explicitly commits.
