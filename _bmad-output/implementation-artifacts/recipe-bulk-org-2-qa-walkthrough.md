# recipe-bulk-org-2 — QA walkthrough

**Story:** Backend `BulkMoveRecipes` response now carries
`prior_recipe_book_id` per moved recipe.

This is a backend-only change. There is no UI to test. Verify against a
running API.

## Setup

- `docker compose up` (api + postgres).
- A user with two writable books and ≥ 2 recipes split across them.

## Manual checks

```bash
# Replace <BEARER>, <SRC_BOOK>, <DEST_BOOK>, <R1>, <R2>.
curl -s -X POST http://localhost:8000/v1/recipes/bulk/move \
  -H "Authorization: Bearer <BEARER>" \
  -H "Content-Type: application/json" \
  -d '{"recipe_ids":["<R1>","<R2>"], "destination_book_id":"<DEST_BOOK>"}' \
  | jq .
```

Expected:

- `moved_count` equals the number of recipes that actually moved
  (`len(moved)`).
- Each item in `moved` has the shape
  `{ "id": "...", "prior_recipe_book_id": "<SRC_BOOK>" }`.
- A recipe already in `<DEST_BOOK>` is silently skipped (absent from
  `moved`, doesn't count toward `moved_count`).
- A 403 / 404 is unchanged from the pre-story behaviour.

## Regression

- [ ] Existing `moved_count` consumers (story 1 home undo flow, recipe
      book detail screen `_bulkMove`) continue to work — the field is
      preserved.
- [ ] `services/api/tests/test_recipe.py::TestBulkMoveRecipes` — all 7
      tests pass under `npx nx run api:test`.
- [ ] 100% coverage maintained on `bulk_move_recipes.py`.
