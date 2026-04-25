# recipe-list-org-1 — Backend: `last_cooked` on list responses + sort + index

**Epic:** `epic-recipe-list-organization`
**Status:** in-progress
**Order in epic:** 1 of 6 (backend foundation — stories 3/4 depend on this surface)

## Why

The table-view + dynamic-column UX (stories 3-4) hinges on `last_cooked` being
available on every recipe in the list payload, and on the list being sortable
by it. The lateral join from `recipes` to `cooking_logs` is the single biggest
risk in the epic — index it correctly the first time, and pin a p95 budget so
the change is reversible if it regresses.

## Scope — files this story touches

**NEW**
- `services/migrator/migrations/versions/20260425010000_index_cooking_logs_recipe_id_cooked_at.py`
  — partial index on `cooking_logs (recipe_id, cooked_at DESC) WHERE archived_at IS NULL`.
- `_bmad-output/implementation-artifacts/recipe-list-org-1-backend-last-cooked-on-list-responses-sort-and-index.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-list-org-1-backend-last-cooked-on-list-responses-sort-and-index-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `services/api/src/api/v1/recipe/list_recipes.py` — add lateral join for
  `last_cooked`; expose `last_cooked: datetime | null` on the row; accept
  `sort=last_cooked|name|created_at`, `dir=asc|desc`; default sort = name asc.
- `services/api/src/api/v1/recipe_book/get_recipe_book.py` — add `last_cooked`
  to each recipe in the embedded `recipes[]` list (this is the path the
  Flutter home-content provider uses today).
- `services/api/tests/test_recipe.py` — extend `list_recipes` tests with
  `last_cooked` payload + sort coverage.
- `services/api/tests/test_recipe_book.py` — extend `get_recipe_book` tests
  with `last_cooked` in the embedded recipes payload.

## Acceptance criteria

1. `GET /v1/recipe-books/{book_id}/recipes` returns `last_cooked: datetime | null`
   per row, sourced from `MAX(cooking_logs.cooked_at)` joined per recipe and
   filtered to `archived_at IS NULL`.
2. The same endpoint accepts `?sort=last_cooked&dir=desc|asc`. `desc` sorts
   `NULLS LAST`; `asc` sorts `NULLS FIRST`. Other allowed sorts: `name`
   (default), `created_at`. Invalid `sort`/`dir` → 400.
3. `GET /v1/recipe-books/{book_id}` (which embeds recipes[]) returns
   `last_cooked` on each recipe item.
4. Migration adds `ix_cooking_logs_recipe_id_cooked_at` partial index.
5. 100% coverage on touched code (api project keeps coverage gate green).
6. Manual perf check: p95 of `GET /v1/recipe-books/{book_id}/recipes` does
   not regress > 50ms vs. pre-change baseline (run `analyze_latency.py
   --section endpoints --window 24h` before push and compare).

## Implementation notes

- The lateral join is the right shape:
  ```sql
  LEFT JOIN LATERAL (
    SELECT MAX(cooked_at) AS cooked_at
    FROM cooking_logs
    WHERE recipe_id = recipes.id AND archived_at IS NULL
  ) cl ON TRUE
  ```
  In SQLAlchemy 2.0 async, we express this as a correlated scalar subquery:
  `select(func.max(CookingLog.cooked_at)).where(CookingLog.recipe_id == Recipe.id, CookingLog.archived_at.is_(None)).correlate(Recipe).scalar_subquery()`.
  Both compile to equivalent plans on PG16; the scalar-subquery form is
  simpler and keeps the existing query shape intact.
- The cooking_logs table currently has no index on `(recipe_id, cooked_at)`.
  Add one as a partial index excluding archived rows — that's the predicate
  the join uses. DESC ordering on `cooked_at` matches the sort direction.
- `sort=last_cooked` requires that the scalar-subquery be in the SELECT list
  (so it can be aliased and referenced in ORDER BY). Use a labeled column.
- For `nulls_last()` / `nulls_first()`, SQLAlchemy provides
  `column.desc().nulls_last()` and `column.asc().nulls_first()`.
- Default sort stays `name asc` — this is the existing behaviour. Don't
  change that without an epic-level decision.
- Validation: keep enums tight. Accept literal strings; reject anything else
  with a 400 + `ErrorCode.INVALID_REQUEST`.

## Test plan (red → green)

1. **T1 — payload includes `last_cooked`.** Seed a recipe with one cooking
   log; call list_recipes; assert `items[0].last_cooked` matches the log's
   `cooked_at`.
2. **T2 — `last_cooked` is null for never-cooked recipe.**
3. **T3 — only most-recent log counts.** Seed two logs for the same recipe
   on different days; assert `last_cooked` = the more-recent one.
4. **T4 — archived logs are ignored.** Seed a log, archive it; assert the
   recipe's `last_cooked` is null.
5. **T5 — sort=last_cooked desc with NULLS LAST.** Three recipes: one with
   recent log, one with older log, one never cooked. Assert order [recent,
   older, null].
6. **T6 — sort=last_cooked asc with NULLS FIRST.** Same fixture, opposite
   order: [null, older, recent].
7. **T7 — sort=name (default) unchanged.** Existing alpha-sort assertions
   stay green.
8. **T8 — invalid sort/dir → 400.**
9. **T9 — get_recipe_book embeds last_cooked.** One recipe with a log; call
   get_recipe_book; assert `recipes[0].last_cooked` is set.
10. **T10 — migration adds index.** Run check-models locally to confirm
    no Alembic drift.

## Out of scope (next stories)

- Hide-in-meals filter / `total_in_meals` count → story 2.
- Frontend toggle, table tile, dynamic column → stories 3-4.
- Empty-state when filter hides everything → story 5.
- Long-press multi-select regression sweep → story 6.

## Risks / open questions

- **SQLAlchemy correlated subquery shape on async session.** The scalar
  subquery must be `.correlate(Recipe)` so SA emits the right SQL. If the
  test driver (SQLite for unit tests, real PG only for check-models)
  rejects the shape, fall back to `LATERAL` via `text()`. The unit-test
  driver is what we'll find out first.
- **Coverage on the new sort branches.** Each `(sort, dir)` arm needs a
  test; otherwise the api 100% gate trips downstream.
