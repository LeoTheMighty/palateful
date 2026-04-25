# import-dup-1 — QA Walkthrough

**Story:** `import-dup-1-backend-duplicate-match-query-and-response-extension`
**Date:** 2026-04-25

## Summary

Foundation story for `epic-import-duplicate-detection`. Computes
"you already have this" matches server-side and embeds them in
`GET /v1/import-items/{id}` so the Approve-Import banner can render
before the user taps Approve. Match keys: case-insensitive title
+ source URL. Backed by a new partial expression index
`ix_recipes_book_lower_name`.

## Files

| File | Status | Purpose |
|---|---|---|
| `services/api/src/api/v1/import_job/_duplicate_match.py` | new | `find_duplicate_recipes` helper + `DuplicateMatch` TypedDict |
| `services/api/src/api/v1/import_job/get_import_item.py` | modified | Embed `duplicate: {matches: [...]}` in response; `_safe_find_duplicates` graceful-degrade shim |
| `libraries/utils/utils/models/recipe.py` | modified | Add `Index("ix_recipes_book_lower_name", ...)` so `alembic check` stays clean |
| `services/migrator/migrations/versions/20260425020000_add_recipe_lower_name_index.py` | new | `CREATE INDEX CONCURRENTLY` for the title match |
| `services/api/tests/test_import.py` | modified | New `TestGetImportItemDuplicateBlock` (10 tests) + `test_cursor_with_non_uuid_row_id_returns_400` × 3 (carry-over) |
| `services/api/tests/test_user_activity.py` | modified | `test_cursor_with_non_uuid_row_id_returns_400` (carry-over) |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | `import-dup-1-...: backlog → done` |
| `_bmad-output/implementation-artifacts/import-dup-1-backend-duplicate-match-query-and-response-extension.md` | new | Story spec |
| `_bmad-output/implementation-artifacts/import-dup-1-backend-duplicate-match-query-and-response-extension-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 Helper signature + return shape | `find_duplicate_recipes(database, user_id, parsed_title, parsed_source_url) -> list[DuplicateMatch]` with all 7 fields | `_duplicate_match.py` |
| AC #2 GET response includes `duplicate.matches` array | `test_duplicate_block_empty_when_no_match` confirms always-present empty array | `test_import.py` |
| AC #3 Index `ix_recipes_book_lower_name` exists | `alembic check` clean after `alembic upgrade head` runs the new migration | `20260425020000_add_recipe_lower_name_index.py` |
| AC #4 Performance — query is index-backed | EXPLAIN-equivalent: single index seek per (book_id, lower-trimmed-title) — no perf test added (DB is mocked in tests) | inspection |
| AC #5 100% coverage on touched code | `nx run api:test` — 2541 pass, 100.00% coverage | nx report |

## Manual QA checklist (single operator, ~10 min)

Run against local stack (`docker compose up`) with one user that has
≥2 recipes in their library, and one of them archived. The new index
landed via `nx run migrator:migrate` (or stack restart applies it).

### Case A — No match (regression)

1. Open the app, start an import (URL or paste-text) of a recipe whose
   name does NOT match anything in your library.
2. Wait for parsing to finish; tap into the Approve-Import screen.
3. **Expect:** standard form. No banner above. Single `Approve` button
   at the bottom.

### Case B — Active title match

1. Pick an existing active recipe — note its name and book.
2. Start a new import (any source) where the parsed title equals
   that recipe's name (case-insensitive, trim-tolerant — extra
   whitespace OK).
3. Open the Approve-Import screen.
4. **Expect:** *(banner UI ships in story 3 — for now verify the API
   directly)* `curl GET /v1/import-items/{id}` includes:
   ```json
   "duplicate": {
     "matches": [
       {
         "recipe_id": "...",
         "title": "...",
         "current_book_id": "...",
         "current_book_name": "...",
         "archived_at": null,
         "last_cooked": "..." or null,
         "match_kind": "title"
       }
     ]
   }
   ```

### Case C — Archived title match

1. Pick an archived recipe (one you previously archived).
2. Re-import a recipe with the same title.
3. **Expect:** GET response shows the match with `archived_at` set
   (ISO8601 timestamp). `match_kind = "title"`.

### Case D — URL match, different title

1. Pick an existing recipe imported from URL `X`.
2. Re-import URL `X` again, but during the parse manually edit the
   title to something different.
3. **Expect:** GET response shows match with `match_kind = "source_url"`
   and the title in the response is the *existing* recipe's title (not
   the parsed one).

### Case E — Multi-match sort

1. Have two recipes with the same name — one active, one archived.
2. Re-import a recipe with that name.
3. **Expect:** `matches[0]` is the active one (sorted first).

### Case F — Failing-open

1. Temporarily break the SQL by swapping `Recipe.name` to a non-existent
   column in `_duplicate_match.py` (don't commit).
2. Open Approve-Import screen.
3. **Expect:** screen still loads with full parsed recipe form. GET
   response shows `"duplicate": {"matches": []}`. Error_log table gets
   one entry with the bad-SQL traceback.
4. Revert the change.

## Test inventory

10 new tests in `TestGetImportItemDuplicateBlock`, all passing:

| # | Test | What it proves |
|---|---|---|
| 1 | `test_duplicate_block_empty_when_no_match` | Block always present, even when empty |
| 2 | `test_duplicate_block_active_title_match` | Case-insensitive + trim normalisation; full row shape |
| 3 | `test_duplicate_block_archived_title_match` | Archived match surfaces archived_at |
| 4 | `test_duplicate_block_url_only_when_parsed_title_blank` | URL match without any title still works |
| 5 | `test_duplicate_block_url_match_overrides_title_difference` | URL match with different titles |
| 6 | `test_duplicate_block_user_edits_title_overrides_parsed` | user_edits.name wins over parsed_recipe.name |
| 7 | `test_duplicate_block_active_sorts_above_archived` | Sort: active first |
| 8 | `test_duplicate_block_empty_when_no_title_or_url` | No-match short-circuit (no DB hit) |
| 9 | `test_duplicate_block_empty_when_user_has_no_books` | No memberships short-circuit |
| 10 | `test_duplicate_block_degrades_on_helper_failure` | DB exception → [] not 500 |

Plus 4 carry-over coverage tests (`test_cursor_with_non_uuid_row_id_returns_400`)
to back-fill 8 lines uncovered by `607c6d0` (parallel /dev loop) and
keep CI's 100% gate green.

## Local CI

| Gate | Result |
|---|---|
| `nx run api:lint` | green |
| `nx run migrator:lint` | green |
| `nx run utils:lint` | green |
| `nx run api:test` | 2541 pass, 100.00% coverage |
| `alembic check` (explicit `DATABASE_URL`) | "No new upgrade operations detected" |

## Known issues / follow-ups

- **None blocking the next story.**
- Local-env-only: `nx run migrator:check-models` fails because my
  `.env` has a psycopg2-incompatible DSN (`?schema=public`). Running
  `bash check_models.sh` with explicit `DATABASE_URL` works. CI is
  unaffected.
