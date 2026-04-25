# recipe-defaults-1 — QA Walkthrough

**Story:** `recipe-defaults-1-backend-is-system-column-and-trying-out-seed-migration`
**Date:** 2026-04-25

## Summary

Foundation story for `epic-recipe-default-books`. Adds the
`is_system: bool` column to `recipe_books`, ships an idempotent
back-fill that seeds one `Trying Out` book per existing user, surfaces
`is_system` on the list + detail endpoints, and locks down the
mutation surfaces (update / delete / archive) so a system book cannot
be renamed, deleted, or archived. Story 2 wires the new-user
provisioning hook on top of this foundation; stories 3 + 4 are the
Flutter switcher pin and the share-import fallback audit.

## Files

| File | Status | Purpose |
|---|---|---|
| `libraries/utils/utils/models/recipe_book.py` | modified | Add `is_system` column with `nullable=False, server_default=false()` |
| `services/migrator/migrations/versions/20260425000000_add_is_system_and_seed_trying_out.py` | new | Schema column + idempotent per-user `Trying Out` seed |
| `services/api/src/api/v1/recipe_book/list_recipe_books.py` | modified | Return `is_system` in each list row |
| `services/api/src/api/v1/recipe_book/get_recipe_book.py` | modified | Return `is_system` in single-book response |
| `services/api/src/api/v1/recipe_book/update_recipe_book.py` | modified | Guard: 400 + `INVALID_REQUEST` on system book |
| `services/api/src/api/v1/recipe_book/delete_recipe_book.py` | modified | Guard: 400 + `INVALID_REQUEST` on system book |
| `services/api/src/api/v1/recipe_book/archive_recipe_book.py` | modified | Guard: 400 + `INVALID_REQUEST` on system book |
| `services/api/tests/test_recipe_book.py` | modified | New `TestSystemBookGuards` class — 6 tests |
| `services/api/tests/conftest.py` | modified | `MockRecipeBook` defaults gain `is_system: False` |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | `recipe-defaults-1-...: backlog → done` |
| `_bmad-output/implementation-artifacts/recipe-defaults-1-backend-is-system-column-and-trying-out-seed-migration.md` | new | Story spec |
| `_bmad-output/implementation-artifacts/recipe-defaults-1-backend-is-system-column-and-trying-out-seed-migration-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 Model column | model definition + 6 tests in `TestSystemBookGuards` | `recipe_book.py` |
| AC #2 Migration upgrade | manual `alembic upgrade head` against local `test` DB; data-fill executed cleanly | `20260425000000_add_is_system_and_seed_trying_out.py` |
| AC #3 Migration downgrade | inspection only — `op.drop_column` is the trivial inverse | migration file |
| AC #4 Idempotency | seed query uses `WHERE NOT EXISTS (...)` + per-batch SELECT — re-run is a no-op | migration file |
| AC #5 `alembic check` clean | `alembic check` against migrated test DB — "No new upgrade operations detected" | local run |
| AC #6 List endpoint | `test_list_recipe_books_includes_is_system` | `test_recipe_book.py` |
| AC #7 Get endpoint | `test_get_recipe_book_includes_is_system` | `test_recipe_book.py` |
| AC #8 Update guard | `test_update_recipe_book_rejects_system_book` | `test_recipe_book.py` |
| AC #9 Delete guard | `test_delete_recipe_book_rejects_system_book` | `test_recipe_book.py` |
| AC #10 Archive guard | `test_archive_recipe_book_rejects_system_book` | `test_recipe_book.py` |
| AC #11 Create guard | `test_create_recipe_book_ignores_is_system_param` | `test_recipe_book.py` |
| AC #12 Coverage | Touched files all at 100% line coverage in `coverage.xml` | nx report |
| AC #13 Lint | `nx run api:lint`, `nx run migrator:lint`, `nx run utils:lint` | all green |
| AC #14 Tests | `nx run api:test` — 2507 pass; `nx run utils:test` — 602 pass | nx report |
| AC #15 Sprint-status flipped | `git diff` sprint-status.yaml | `backlog → done` |

## Test inventory (6 new tests, all passing)

| # | Test | What it proves |
|---|---|---|
| 1 | `test_list_recipe_books_includes_is_system` | List response surfaces `is_system` per row; `True` and `False` both round-trip. |
| 2 | `test_get_recipe_book_includes_is_system` | Single-book response includes `is_system: True` for a system book. |
| 3 | `test_update_recipe_book_rejects_system_book` | 400 + body `error_message` mentioning "system" when owner tries to PUT a system book. |
| 4 | `test_delete_recipe_book_rejects_system_book` | 400 + body `error_message` mentioning "system" when owner tries to DELETE a system book. |
| 5 | `test_archive_recipe_book_rejects_system_book` | 400 + body `error_message` mentioning "system" when owner tries to archive a system book. |
| 6 | `test_create_recipe_book_ignores_is_system_param` | Posting `{"name": "X", "is_system": true}` yields a 201; `is_system` is not in the response (Pydantic Params doesn't expose the field, so it is silently dropped). |

## Manual QA (runtime sanity)

1. **Local DB migration end-to-end.** Ran on the dockerized `palateful-db-1` against the `test` database:
   ```bash
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test \
       poetry run alembic upgrade head
   ```
   Result: revision `rdb1isys001` (head). `alembic check` → "No new upgrade operations detected." Model and migration are in lockstep.

2. **Idempotent re-run sanity** (manual). The back-fill loop's outer `WHERE NOT EXISTS (... is_system=true ...)` predicate guarantees that running the migration twice (or partially-failing then retrying) does not duplicate rows. No automated test for this — the migration file is single-revision-per-deploy and the predicate's correctness is reviewable in isolation.

3. **No `default_recipe_book_id` mutation.** Confirmed by inspection of the migration's upgrade body: there is no `UPDATE users` statement. Existing users keep their current default (often the onboarding-flow "My Recipes" book). Story 2 sets the new-user-only default; story 4 audits NULL-default edge cases.

## Adversarial review findings (fixed before commit)

1. **Migration's `INSERT INTO recipe_book_users` included a non-existent `id` column.**
   `recipe_book_users` is a join table with composite PK
   `(user_id, recipe_book_id)` and no `id` column (per `JoinsBase`,
   not `Base`). The initial migration draft inserted
   `(id, created_at, updated_at, recipe_book_id, user_id, role)` with
   `gen_random_uuid()` for id — would have failed at the first user
   in production. Caught only because the local test DB had zero
   users when the original draft was first applied (the seed loop
   never executed an INSERT on the empty user set).
   **Fix:** dropped `id` from the column list and `gen_random_uuid()`
   from the VALUES clause — matches the model's composite-PK shape.
   Re-verified end-to-end: created a synthetic user, dropped the
   `is_system` column, re-applied the migration, confirmed exactly
   one Trying Out book + owner membership row land per user.

## Risks known to oncall / future stories

- **Existing user-named books titled "Trying Out".** A user who happens to have a personal book named `Trying Out` will end up with two rows of the same name — one with `is_system=True` and one with `is_system=False`. The Flutter switcher (story 3) sorts by `is_system DESC` so the system one shows up in the System section regardless. No collision in DB integrity terms.
- **Migration ordering with parallel epics.** This migration's `down_revision = "unreadnotifidx1"`. If a parallel `aam-` or other epic merges first and adds another head, this revision is rebased onto the new head before merge. Standard alembic conflict resolution.
- **No partial unique index.** We deviated from the epic text on this point (documented in spec). App-level idempotency in both the migration and story 2's hook covers the duplicate-seed case. Cross-table unique constraints aren't expressible in standard Postgres.

## Done

- [x] `nx run api:lint` green.
- [x] `nx run migrator:lint` green.
- [x] `nx run utils:lint` green.
- [x] `nx run api:test` — 2507/2507 pass; touched files at 100% coverage. The two pre-existing uncovered gaps (`list_import_items.py:150-151` and friends) are from a parallel session's untracked WIP and are NOT in this story's File List.
- [x] `nx run utils:test` — 602/602 pass.
- [x] `alembic check` (local test DB) — no drift.
- [x] `sprint-status.yaml` flipped `recipe-defaults-1-...: backlog → done`.
- [x] Adversarial review pass complete; no findings deferred.
- [x] Atomic commit — only story-scoped files staged.
