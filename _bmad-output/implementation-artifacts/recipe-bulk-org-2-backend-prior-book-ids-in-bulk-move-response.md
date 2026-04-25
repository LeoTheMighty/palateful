# recipe-bulk-org-2 — Backend: prior-book-ids in bulk-move response

**Epic:** `epic-recipe-bulk-organize`
**Status:** review
**Order in epic:** 2 of 5

## Why

Story 1 captures each recipe's prior book id **client-side** (from the
home content cache) before issuing the bulk move, so an Undo can put
each recipe back where it came from. That works on Home, where the cache
exists, but the recipe-detail pill row (story 4) and any future caller
that doesn't already have the recipe in memory would have to re-fetch
each row to know its prior book.

Story 2 augments the bulk-move response to carry the prior book id per
moved recipe. After this story the response shape is:

```json
{
  "moved_count": 2,
  "moved": [
    { "id": "recipe-1", "prior_recipe_book_id": "src-a" },
    { "id": "recipe-2", "prior_recipe_book_id": "src-b" }
  ]
}
```

Recipes already in the destination book are skipped (idempotent
behaviour, unchanged) and do **not** appear in `moved`.

## Scope — files this story touches

**MODIFY**
- `services/api/src/api/v1/recipe/bulk_move_recipes.py` — capture
  `prior_book_id` per recipe before the FK swap; return them in the
  new `moved: list[MovedItem]` field. `moved_count` is preserved for
  backwards-compatibility (existing clients keep using it).
- `services/api/tests/test_recipe.py` — extend the existing
  `test_bulk_move_success` and `test_bulk_move_skips_already_in_dest`
  to assert on the new payload, and add
  `test_bulk_move_returns_distinct_prior_book_ids` for the
  multi-source-book selection case (acceptance hook for story 3).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  this story `backlog → done`.

**NEW**
- `_bmad-output/implementation-artifacts/recipe-bulk-org-2-backend-prior-book-ids-in-bulk-move-response.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-bulk-org-2-qa-walkthrough.md`
  (QA checklist).

### Out of scope

- Flutter wiring for the new field. The Story 1 client captures prior
  ids from local cache and ignores the response; the recipe-detail pill
  row (story 4) will pick the field up when it lands.
- Schema changes — this is a pure response-shape augmentation. No
  migration needed.

## How

The endpoint already iterates the input recipe ids, validates source
membership, and sets `recipe.recipe_book_id = params.destination_book_id`
on each. The change captures the recipe id + its CURRENT
`recipe_book_id` (as a string — the column is a UUID) into a
`list[tuple[Recipe, str]]` BEFORE the FK swap, then formats that list
as `MovedItem`s in the response. Skipped recipes (already in dest)
never enter the list.

Two new Pydantic classes:

- `BulkMoveRecipes.MovedItem(BaseModel)` — `{id: str, prior_recipe_book_id: str}`.
- `BulkMoveRecipes.Response.moved: list[MovedItem] = Field(default_factory=list)` —
  empty when no recipes actually moved.

Backwards-compatible: clients that parse only `moved_count` continue to
work.

## Acceptance

- `moved_count` matches `len(moved)` for the success path.
- Each `moved[i].prior_recipe_book_id` equals the recipe's
  `recipe_book_id` *prior to* the FK swap.
- Multi-source selection (recipes from books A and B → book C) returns
  distinct prior ids per recipe.
- Skipped (already-in-dest) recipes are absent from `moved` and do not
  count toward `moved_count`.
- 100% line coverage maintained on `bulk_move_recipes.py`.

## Test plan

- Unit (already in `test_recipe.py`):
  - `test_bulk_move_success` — same-source case, asserts both
    `moved_count == 2` and `moved` carries the right prior id.
  - `test_bulk_move_skips_already_in_dest` — skipped recipe absent
    from `moved`.
  - `test_bulk_move_returns_distinct_prior_book_ids` — multi-source
    case, asserts per-recipe distinct prior ids.
