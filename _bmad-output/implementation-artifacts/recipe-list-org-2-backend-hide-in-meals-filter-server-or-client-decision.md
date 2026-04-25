# recipe-list-org-2 — Backend: hide-in-meals filter (server / client decision)

**Epic:** `epic-recipe-list-organization`
**Status:** in-progress
**Order in epic:** 2 of 6

## Audit + decision

The home payload already carries `component_recipe_ids` on each
`MealSummaryResponse` (`services/api/src/api/v1/meal/_response.py:103`),
so the home grid can derive "is this recipe in a meal?" purely
client-side by unioning component_recipe_ids across the meals it
already loaded.

The **book-detail screen** is the gap. `GET /v1/recipe-books/{id}` and
`GET /v1/recipe-books/{id}/recipes` both return recipes without loading
the meals that reference them. Story 5 needs the chip ("*N recipes · M
hidden in meals*") on the book-detail surface too — and we can't ask
the client to over-fetch meals just to compute the chip count.

**Decision:** surface meal-membership directly on the recipe row.

- Add `is_in_meal: bool` to each `RecipeItem` in both endpoints, via a
  bulk EXISTS-style aggregate on `meal_recipes` (one round-trip per
  page, mirroring the `last_cooked` aggregate from story 1).
- Add `total_in_meals: int` to the list response so the chip copy renders
  without a second call.
- **No `?hide_in_meals=true` query param.** Filtering happens on the
  client, same as the existing favorites + tag chips today (`pfc-4`
  guarantee: filter flips don't refetch). Server-side filtering
  collides with pagination — `total_in_meals` would mismatch the
  filtered `total` and the client would have to reconcile two counts
  per call.

## Scope — files this story touches

**NEW**
- `_bmad-output/implementation-artifacts/recipe-list-org-2-backend-hide-in-meals-filter-server-or-client-decision.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-list-org-2-backend-hide-in-meals-filter-server-or-client-decision-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `services/api/src/api/v1/recipe/list_recipes.py` — add `is_in_meal`
  per-row via bulk meal_recipes lookup; add `total_in_meals` on the
  response.
- `services/api/src/api/v1/recipe_book/get_recipe_book.py` — same
  fields on the embedded recipes + a `total_in_meals` count on the
  response shape.
- `services/api/tests/test_recipe.py` — extend list_recipes coverage.
- `services/api/tests/test_recipe_book.py` — extend get_recipe_book
  coverage.

## Acceptance criteria

1. `GET /v1/recipe-books/{book_id}/recipes` returns:
   - `items[].is_in_meal: bool` — true if at least one **non-archived**
     `meal_recipes` row exists with `recipe_id = recipe.id` and the
     parent meal is **non-archived**.
   - `total_in_meals: int` — count of recipes in this book that have
     `is_in_meal = true`. Matches the chip copy.
2. `GET /v1/recipe-books/{book_id}` returns the same per-recipe field
   on the embedded `recipes[]` list, plus `total_in_meals` at the top
   level.
3. A recipe attached to one meal is `is_in_meal=true`. Once the meal is
   archived, that same recipe falls back to `is_in_meal=false`.
4. 100% coverage on touched code.
5. Performance — the new aggregate must not regress p95 by > 50ms (same
   gate as story 1).

## Implementation notes

- Pattern mirrors story 1's last_cooked aggregate: one `SELECT
  recipe_id FROM meal_recipes JOIN meals ON ... WHERE recipe_id IN
  (...page) AND meal_recipes.archived_at IS NULL AND
  meals.archived_at IS NULL` per page; build a `set` of recipe_ids
  that have a meal; mark each row.
- For `total_in_meals`, run one extra count query scoped to the
  book's recipes — `COUNT(DISTINCT recipe_id) FROM meal_recipes WHERE
  recipe_id IN (book's recipe_ids) AND ...`. Alternative: count over
  the per-page set + scope the count query to the same predicates the
  list query uses. We pick the latter so the count is correct across
  pagination boundaries.
- `meal_recipes` already has `ix_meal_recipes_recipe_id` (confirmed in
  the model file). No new index needed.
- The existing `meal_recipes` row can survive after a Meal is
  archived (cascade is set to `RESTRICT` on the recipe FK; archive is
  a soft-delete that doesn't drop the join row). So we **must** join
  through to `meals.archived_at IS NULL` to honor the rule "an
  archived meal no longer hides its recipes".

## Test plan

1. **T1 — recipe in one meal → is_in_meal=true, total_in_meals=1.**
2. **T2 — recipe in zero meals → is_in_meal=false.**
3. **T3 — recipe was in a meal, meal then archived → is_in_meal=false.**
4. **T4 — total_in_meals counts distinct recipes (a recipe in 2 meals
   counts once).**
5. **T5 — empty book → total_in_meals=0, no extra round-trips.**
6. **T6 — get_recipe_book embeds is_in_meal + total_in_meals.**

## Out of scope

- Frontend chip + counter → story 5.
- Server-side filter (`?hide_in_meals=true`) — explicitly rejected
  above; revisit if pagination + chip ever conflict.
