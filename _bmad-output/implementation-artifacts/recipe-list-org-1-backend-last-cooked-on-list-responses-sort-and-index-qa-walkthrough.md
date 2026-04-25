# recipe-list-org-1 — QA Walkthrough

**Story:** Backend `last_cooked` on list responses + sort + index
**Epic:** `epic-recipe-list-organization`
**Status:** review

## Pre-flight (one-time)

Run after pulling the branch and before exercising the QA checklist:

```bash
docker compose --profile migrate up migrator   # apply ix_cooking_logs_recipe_id_cooked_at_active
docker compose up                              # boot api + db
```

If you're working on a fresh DB, seed at least one recipe via the
existing share-import or onboarding flow before exercising the
table-shape assertions below.

## Smoke

| # | Step | Expected |
|---|------|----------|
| 1 | `GET /v1/recipe-books/{book_id}/recipes` against a book that has at least one recipe | 200; each `items[].last_cooked` is `null` for never-cooked recipes, ISO datetime for cooked ones |
| 2 | Trigger a Cook-mode session that writes a `cooking_logs` row for one of the recipes, then re-issue the list call | The same recipe's `last_cooked` is now populated, matches the new log's `cooked_at` |
| 3 | `GET /v1/recipe-books/{book_id}/recipes?sort=last_cooked&dir=desc` | 200; recipes with logs come first ordered most-recent → oldest, then never-cooked recipes at the bottom (NULLS LAST) |
| 4 | `GET /v1/recipe-books/{book_id}/recipes?sort=last_cooked&dir=asc` | 200; never-cooked recipes appear first (NULLS FIRST), then logs ordered oldest → newest |
| 5 | `GET /v1/recipe-books/{book_id}/recipes?sort=name&dir=asc` (default behaviour) | 200; alpha-sorted, identical to pre-change behaviour |
| 6 | `GET /v1/recipe-books/{book_id}/recipes?sort=created_at&dir=desc` | 200; ordered newest → oldest by `created_at` |
| 7 | `GET /v1/recipe-books/{book_id}/recipes?sort=garbage` | 400 with `INVALID_REQUEST` |
| 8 | `GET /v1/recipe-books/{book_id}/recipes?dir=sideways` | 400 with `INVALID_REQUEST` |
| 9 | `GET /v1/recipe-books/{book_id}` (book detail) | 200; each `recipes[].last_cooked` is populated alongside `name`, `image_url`, etc. |

## Edge cases

| # | Step | Expected |
|---|------|----------|
| E1 | Archive an existing cooking_log row (`UPDATE cooking_logs SET archived_at = now() WHERE id = ...`), re-issue list call | The recipe's `last_cooked` reflects the most-recent **non-archived** log; if all logs are archived, `last_cooked` becomes `null` |
| E2 | Recipe with two cooking_log rows from different days | `last_cooked` = the most-recent of the two |
| E3 | Empty book (no recipes) | `items` empty, `total = 0`, no extra DB round-trips fired (favorites + last_cooked aggregates short-circuit on empty page) |
| E4 | User without access to the book | 403 with `RECIPE_BOOK_ACCESS_DENIED` (regression — pre-change behaviour) |
| E5 | List on a book where every recipe has `last_cooked = null` and sort = `last_cooked desc` | All rows present, deterministic order (DB tie-break on the implicit primary key — same as pre-change for any all-equal sort key) |

## Performance

Capture a baseline before merging:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section endpoints --window 24h --format csv > /tmp/baseline.csv
```

Then post-deploy:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section endpoints --window 24h --format csv > /tmp/post-merge.csv
diff <(grep -E 'recipe-books/.+/recipes|recipe-books/[^/]+$' /tmp/baseline.csv) \
     <(grep -E 'recipe-books/.+/recipes|recipe-books/[^/]+$' /tmp/post-merge.csv)
```

**Pass criterion:** p95 of `GET /v1/recipe-books/{book_id}/recipes` and
`GET /v1/recipe-books/{book_id}` does not regress > 50ms.

## Regression sweep

| # | Step | Expected |
|---|------|----------|
| R1 | Existing search filter (`?search=pasta`) still works | 200, only matching items |
| R2 | Existing vibe filter (`?vibe=cozy`) still works | 200 |
| R3 | Pagination (`?limit=10&offset=10`) still works | 200, correct slice |
| R4 | Existing tags array on each item still serializes | unchanged |
| R5 | Existing favorite-flag bulk join still works | `is_favorite` still set when applicable |

## Known parallel-session note

`epic-recipe-bulk-organize` is being implemented concurrently in this
working tree. Their migration `20260425010000_add_recipe_lower_name_index.py`
chains off the same `rdb1isys001` revision as ours
(`20260425010000_index_cooking_logs_recipe_id_cooked_at.py`). Locally,
`npx nx run migrator:check-models` fails with "Multiple head revisions
are present" — that's the two-untracked-WIP collision, not a defect in
this story. CI on a clean checkout sees only the merged history; if
both stories land independently, the **second** one to merge will need
to rebase its `down_revision` to chain off the first.
