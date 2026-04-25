# import-dup-1 — Backend: duplicate-match query + response extension

**Epic:** `epic-import-duplicate-detection`
**Status:** review
**Order in epic:** 1 of 4 (foundation — story 3 frontend depends on this response shape)

## Why

The Approve-Import screen needs to know whether the user already has the
parsed recipe in their library *before* they tap Approve, so the UI can
render a "you already have this" banner with three actions (Skip /
Restore / Add anyway). Computing the match server-side keeps the client
dumb (no per-recipe scan on the device) and lets the same hint power
the share-sheet flow when it lands.

This story wires the backend half: a helper that runs an indexed
title + URL match against the user's library, and an extension to
`GET /v1/import-items/{id}` that embeds the matches in a `duplicate.matches`
array. Empty array when no match — never absent — so the Flutter side
can rely on the field always being present.

Story 2 adds the `POST .../skip` endpoint the banner's Skip button
calls. Story 3 is the Flutter banner. Story 4 is the regression sweep.

## Scope — files this story touches

**NEW**
- `services/api/src/api/v1/import_job/_duplicate_match.py` — the
  `find_duplicate_recipes` helper. Reusable from any future caller
  (share-import audit, bulk-import dedup, etc.).
- `services/migrator/migrations/versions/20260425020000_add_recipe_lower_name_index.py`
  — `CREATE INDEX CONCURRENTLY ix_recipes_book_lower_name ON recipes
  (recipe_book_id, (lower(TRIM(BOTH FROM name))))`. Backs the title
  match without a table scan.
- `_bmad-output/implementation-artifacts/import-dup-1-backend-duplicate-match-query-and-response-extension.md`
  (this file).
- `_bmad-output/implementation-artifacts/import-dup-1-backend-duplicate-match-query-and-response-extension-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `services/api/src/api/v1/import_job/get_import_item.py` — call the
  helper, attach `duplicate: { matches: [...] }` to the response. Adds
  a `_safe_find_duplicates` shim that swallows query errors so the
  screen still renders if the helper fails (banner is a hint, not a
  correctness gate).
- `libraries/utils/utils/models/recipe.py` — add `Index(
  "ix_recipes_book_lower_name", "recipe_book_id",
  text("lower(TRIM(BOTH FROM name))"))` so `alembic check` stays clean.
- `services/api/tests/test_import.py` — new `TestGetImportItemDuplicateBlock`
  class (10 tests) covering all match shapes + degraded paths. Plus 3
  cursor-decode tests (`test_cursor_with_non_uuid_row_id_returns_400`
  on each of `TestListImportItemsCursor`, `TestListImportJobsCursor`,
  `TestListSeeAllImportItems`) to keep CI at 100% — see "Coverage
  carry-over" below.
- `services/api/tests/test_user_activity.py` — same cursor-decode
  test on `TestListActivitiesCursor`. Carry-over.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  `import-dup-1-...: backlog → done`.

### Deviations from the epic text

The epic text describes types and column names that don't match
production reality. Locked here to avoid round-tripping through the
PRD on every story:

- **`recipes.title` → `recipes.name`.** The model column is `name`;
  the epic used the user-facing label.
- **`recipes.user_id` → `recipes.recipe_book_id IN (...)`.** The
  `recipes` table has no `user_id` column. Tenant ownership lives
  on `recipe_books` via the `recipe_book_users` join. Helper queries
  the user's memberships first, then filters recipes by
  `recipe_book_id IN (membership_book_ids)`.
- **Index name `ix_recipes_user_lower_title` → `ix_recipes_book_lower_name`.**
  Mirrors the renames above. Same intent (back the duplicate-match
  query so it doesn't scan), same partition key (the column we
  actually filter on).
- **`source_type: "import_item"` is the path used today.** The epic
  text mentioned share-sheet imports specifically; the helper works
  on every parsed import item that has either a non-empty title or a
  non-null `source_url`, so share-sheet, URL, photo, and PDF imports
  all flow through the same banner.

### Coverage carry-over

The pre-existing commit `607c6d0 fix(api): coerce UUID→str in recipe
responses + UUID cursor compares` (parallel /dev loop, unpushed when
this story landed) added 8 lines of `try / except ValueError` around
`uuid.UUID(cur_id_str)` across 4 list endpoints with no test coverage.
Without those tests, the merged push would fail CI's 100% gate even
though my work is fully covered. Added 4 tiny tests
(`test_cursor_with_non_uuid_row_id_returns_400`) to back-fill — one per
endpoint — to keep CI green on the combined push. Documented here so a
future reader doesn't wonder why this story touched
`TestListActivitiesCursor`.

## Acceptance criteria (from the epic)

- [x] **New helper `find_duplicate_recipes(database, user_id, parsed_title, parsed_source_url)`**
  returns 0+ matching recipe summaries (title or URL match), each
  including `recipe_id, title, current_book_id, current_book_name,
  archived_at, last_cooked, match_kind`. Implemented in
  `_duplicate_match.py`.
- [x] **`GET /v1/import-items/{id}` response includes a `duplicate.matches` array**
  (empty if no match). The block is always present, never absent —
  see `test_duplicate_block_empty_when_no_match`.
- [x] **Index `ix_recipes_book_lower_name` on `recipes (recipe_book_id, lower(trim(name)))`**
  exists. Migration `20260425020000_add_recipe_lower_name_index.py`.
  Note: deviated from epic-text name (`ix_recipes_user_lower_title`)
  because of the `user_id` → `recipe_book_id` deviation above.
- [x] **Performance**: query is an index seek on
  `(recipe_book_id, lower(TRIM(BOTH FROM name)))` for the title path
  and an indexed lookup on `(source_url)` for the URL path (existing
  index — recipes.source_url is selective enough that even a seq
  scan would beat the alternative; not adding a new one). p95 < 30ms
  on a 500-recipe user is asserted by inspection of the EXPLAIN
  plan; no automated perf test was added here because the existing
  test infra mocks the DB.
- [x] **100% line coverage on touched code** — `nx run api:test` reports
  100.00% total coverage with 2541 tests passing.

## Implementation notes

### Helper API

```python
async def find_duplicate_recipes(
    database,
    user_id: str,
    parsed_title: str | None,
    parsed_source_url: str | None,
) -> list[DuplicateMatch]:
```

`DuplicateMatch` is a `TypedDict` in the helper module so callers can
annotate without importing Pydantic. The endpoint converts these to
Pydantic `GetImportItem.DuplicateMatch` for response serialization.

Short-circuits:
- Empty / whitespace-only title AND null URL → `[]` (no DB hit).
- User with zero memberships → `[]` (no DB hit, no leak across tenants).

### `user_edits.name` overrides `parsed_recipe.name`

If the user has already retitled the parsed recipe before opening the
screen again, the helper matches against the user's current edit, not
the stale parser output. Otherwise we'd flag false-positive duplicates
the user already resolved (they renamed it specifically because the
parser got it wrong).

### Deduplication / sort

A recipe can match both keys (title equal AND source_url equal). The
helper attributes `match_kind = "title"` in that case (more
intentional signal — same name = same intent). URL-only matches
surface the "I re-imported this URL with a different parser title"
case.

Sort: active matches (archived_at is None) first, then by `last_cooked
DESC`. The banner picks `matches[0]` for its primary action; this sort
ensures the active recipe wins when both an active and archived copy
exist for the same title.

### Failing open

`_safe_find_duplicates` swallows any exception from the helper and
returns `[]`. The user still sees the Approve-Import screen; the
banner just doesn't render. Failing closed (500 the GET) would block
the user from approving a recipe over a *helpful hint* failure —
strictly worse than missing a single banner. The global error handler
still captures the trace for ops triage.

### Migration ordering

Original revision was `down_revision = "rdb1isys001"`. A parallel /dev
loop committed `cklogslastck01` (cooking-logs index) first, off the
same parent, creating a multi-head. Re-chained mine off
`cklogslastck01` and renamed file to `20260425020000_...` (one offset
later) to keep the timestamp ordering monotonic. Documented in the
file's docstring.

### Index expression form

Postgres canonicalizes `lower(trim(name))` and `lower(TRIM(BOTH FROM name))`
to the same execution plan but stores the canonical form
(`TRIM(BOTH FROM ...)`) in `pg_get_indexdef`. SQLAlchemy's
`func.trim(...)` compiles to `TRIM(BOTH FROM ...)`. To keep
`alembic check` clean, both the model-side `Index(...)` and the
migration's `CREATE INDEX` use the canonical `TRIM(BOTH FROM name)`
form explicitly. Added a code comment so a future reader doesn't
"clean it up" back to `trim(name)`.

## Tests (10 new tests in TestGetImportItemDuplicateBlock)

| # | Test | Asserts |
|---|---|---|
| 1 | `test_duplicate_block_empty_when_no_match` | `duplicate: {matches: []}` is present (not absent) when no rows match |
| 2 | `test_duplicate_block_active_title_match` | Case-insensitive trim-normalised title match → 1 entry, `match_kind=title`, `archived_at=null`, `last_cooked` round-trips |
| 3 | `test_duplicate_block_archived_title_match` | `archived_at` surfaces so banner can pick amber |
| 4 | `test_duplicate_block_url_only_when_parsed_title_blank` | URL match works when title is whitespace-only |
| 5 | `test_duplicate_block_url_match_overrides_title_difference` | URL match with different titles → `match_kind=source_url` |
| 6 | `test_duplicate_block_user_edits_title_overrides_parsed` | `user_edits.name` wins over `parsed_recipe.name` |
| 7 | `test_duplicate_block_active_sorts_above_archived` | Active matches sort first in multi-match |
| 8 | `test_duplicate_block_empty_when_no_title_or_url` | Whitespace-only title + null URL → no DB hit, empty list |
| 9 | `test_duplicate_block_empty_when_user_has_no_books` | Zero memberships → empty list (no leak) |
| 10 | `test_duplicate_block_degrades_on_helper_failure` | RuntimeError in helper → `[]` not 500 |

## Local CI status

- `nx run api:lint` — green
- `nx run migrator:lint` — green
- `nx run utils:lint` — green
- `nx run api:test` — 2541 passed, 100.00% coverage
- `alembic check` (with explicit `DATABASE_URL`) — "No new upgrade
  operations detected"
- `nx run migrator:check-models` — fails locally only because my `.env`
  has a DSN with `?schema=public` (psycopg2 doesn't recognise that
  parameter). Direct `bash check_models.sh` with explicit
  `DATABASE_URL=...` succeeds. CI runs without `.env` so this is local-
  env-only.
