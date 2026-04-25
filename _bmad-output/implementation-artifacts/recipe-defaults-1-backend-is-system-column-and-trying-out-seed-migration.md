# recipe-defaults-1 — Backend: `is_system` column + Trying Out seed migration

**Epic:** `epic-recipe-default-books`
**Status:** review
**Order in epic:** 1 of 4 (foundation — story 2 depends on 1, stories 3/4 depend on 1)

## Why

Three follow-on epics (`epic-recipe-list-organization`, `epic-recipe-bulk-organize`,
`epic-import-duplicate-detection`) all reference a stable system-pinned
"Trying Out" book as the default destination for share-imports and as one
of two opinionated defaults the recipe-book switcher pins above the
user's personal books. Without a way to identify *which* `recipe_books`
row is the system book — and without that book existing for current
users — none of those epics can ship cleanly.

Story 1 lands the schema + back-fill so:

1. The `is_system` flag exists on `recipe_books`, defaulting `false` for
   user-created books.
2. Every existing user has exactly one `Trying Out` book seeded
   (idempotent on re-run).
3. The list endpoint exposes `is_system` so the Flutter switcher (story
   3) can pin the system tile distinctly.
4. The mutation endpoints (`UpdateRecipeBook`, `DeleteRecipeBook`,
   `ArchiveRecipeBook`) refuse to mutate a system book — UI cannot
   accidentally rename / delete / archive Trying Out via existing
   long-press menus.

Story 2 then wires the new-user provisioning hook (Auth0 callback) to
create + default-set the system Trying Out book per new user. Story 3 is
the Flutter switcher pin. Story 4 is the share-import-fallback audit.

## Scope — files this story touches

**NEW**
- `services/migrator/migrations/versions/20260425000000_add_is_system_and_seed_trying_out.py`
  — Alembic migration: column + per-user seed of `Trying Out` + `RecipeBookUser`
  owner row, idempotent.
- `_bmad-output/implementation-artifacts/recipe-defaults-1-backend-is-system-column-and-trying-out-seed-migration.md`
  (this file).
- `_bmad-output/implementation-artifacts/recipe-defaults-1-backend-is-system-column-and-trying-out-seed-migration-qa-walkthrough.md`
  (QA checklist).

**MODIFY**
- `libraries/utils/utils/models/recipe_book.py` — add `is_system: Mapped[bool]`
  field (server_default=false, not null).
- `services/api/src/api/v1/recipe_book/list_recipe_books.py` — include
  `is_system` in the per-row response.
- `services/api/src/api/v1/recipe_book/update_recipe_book.py` — guard:
  reject mutations to `is_system=true` books with 400 / `INVALID_REQUEST`.
- `services/api/src/api/v1/recipe_book/delete_recipe_book.py` — same guard.
- `services/api/src/api/v1/recipe_book/archive_recipe_book.py` — same guard.
- `services/api/src/api/v1/recipe_book/get_recipe_book.py` — include
  `is_system` in the single-book response so the Flutter detail page can
  hide rename/delete affordances.
- `services/api/src/api/v1/recipe_book/create_recipe_book.py` — no
  change required: `CreateRecipeBook.Params` doesn't expose `is_system`,
  so client cannot supply it and the new column server-defaults to
  `false`. T6 below pins this behaviour as a regression guard.
- `services/api/tests/test_recipe_book.py` — extend with system-book
  guard tests (mutation refusal, list response shape).
- `services/api/tests/conftest.py` — `MockRecipeBook` defaults gain
  `is_system: False`.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  `recipe-defaults-1-backend-is-system-column-and-trying-out-seed-migration:
  backlog → done`.

### Out of scope — deliberate deferrals

- **No partial unique index.** The epic text mentions a partial unique
  index `ix_recipe_books_one_system_per_user_per_kind on (user_id, name)
  WHERE is_system=true`. This is impractical: `recipe_books` has no
  `user_id` column — book ownership lives in the `recipe_book_users`
  membership table. A cross-table partial unique constraint isn't
  expressible in standard Postgres. We rely instead on app-level
  idempotency: the migration's seeding loop and story 2's provisioning
  hook both `SELECT` for an existing system book before `INSERT`. This
  matches the precedent set by `_ensure_default_calendar` in
  `services/api/src/dependencies.py` (idempotency via SELECT-before-INSERT
  + SAVEPOINT). Documenting deviation here so reviewers don't flag the
  index's absence.
- **`default_recipe_book_id` not set during this migration.** The
  back-fill seeds a Trying Out book per user but does NOT touch
  `users.default_recipe_book_id`. Existing users keep whatever default
  they had (often the onboarding-flow's "My Recipes" book). Story 2 owns
  the new-user-only default-setting; existing users with `NULL` defaults
  are an out-of-scope edge case that story 4 audits for the Flutter
  share-import path.
- **No new endpoint to mark a book system.** Creating system books is
  internal — driven by the migration here and the provisioning hook in
  story 2. The `CreateRecipeBook` endpoint silently ignores any
  client-supplied `is_system` (no public API surface to set it).
- **No notification side effects on seeded books.** The
  `notify_book_shared` / member-added flows are not triggered by the
  migration. The Trying Out book is owner-only (one membership row, the
  user's), so there's nothing to notify.

## Contract changes

### `RecipeBook` model

```python
class RecipeBook(Base):
    __tablename__ = "recipe_books"
    name: Mapped[str] = ...
    description: Mapped[str | None] = ...
    is_public: Mapped[bool] = ...
    is_shared: Mapped[bool] = ...
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=sa.false()
    )  # NEW
```

### `GET /v1/recipe-books` — response item

Adds `is_system: bool` to each row. Client sorts by
`is_system DESC, last_opened_at DESC` (story 3) without further server-
side support.

### `GET /v1/recipe-books/{id}` — response

Adds `is_system: bool` so the Flutter detail page knows to hide
rename / delete affordances.

### `PUT /v1/recipe-books/{id}` — guard

If the target book has `is_system=true`, returns:

```
400 Bad Request
{ "detail": "Cannot modify a system recipe book", "code": <INVALID_REQUEST> }
```

### `DELETE /v1/recipe-books/{id}` — guard

Same 400 / `INVALID_REQUEST` shape.

### `POST /v1/recipe-books/{id}/archive` — guard

Same 400 / `INVALID_REQUEST` shape.

## Migration (`20260425000000_add_is_system_and_seed_trying_out.py`)

```python
revision = "rdb1isys001"
down_revision = "unreadnotifidx1"   # head as of this story
```

### Upgrade phases

1. **Schema.** `op.add_column('recipe_books', sa.Column('is_system',
   sa.Boolean(), nullable=False, server_default=sa.false()))`.
2. **Back-fill loop**, batches of 500 users:
   - `SELECT id FROM users WHERE id NOT IN (
       SELECT rbu.user_id FROM recipe_book_users rbu
       JOIN recipe_books rb ON rb.id = rbu.recipe_book_id
       WHERE rb.is_system = true AND rb.archived_at IS NULL
       AND rbu.role = 'owner'
     ) LIMIT :batch`
   - For each user_id:
     - `INSERT INTO recipe_books (id, created_at, updated_at, name,
       description, is_public, is_shared, is_system) VALUES
       (gen_random_uuid(), NOW(), NOW(), 'Trying Out', NULL, false,
       false, true) RETURNING id`
     - `INSERT INTO recipe_book_users (id, created_at, updated_at,
       recipe_book_id, user_id, role) VALUES (gen_random_uuid(),
       NOW(), NOW(), :book_id, :user_id, 'owner')`
3. **No update to `users.default_recipe_book_id`** — explicitly skipped.
   Existing users keep their current default.

### Downgrade

`op.drop_column('recipe_books', 'is_system')`. We do NOT delete the
seeded books — they're indistinguishable from user-created books once
the column is gone, and removing them would cascade-delete any recipes
the user added to Trying Out post-seed. Operator must run a hand-rolled
cleanup if a true rollback is required.

### Idempotency

Re-running the migration on an already-upgraded DB is safe:
- The `add_column` step has `nullable=False, server_default=false` so a
  re-run would already error on column existence; Alembic's revision
  graph prevents that.
- The seed loop's `SELECT id FROM users WHERE id NOT IN (...)` is
  evaluated each batch, so users seeded by an earlier (partial) run are
  excluded.

### Concurrency

The seeding loop is sequential and runs inside the migration's outer
transaction. No `CREATE INDEX CONCURRENTLY` because no index is created.
Total work for current dogfood population (~tens of users) is sub-second.
At 10k users (future-proofing), a 500-batch sequential loop is still
under a minute, well below RDS migration timeout.

## Acceptance criteria

1. **Model.** `RecipeBook.is_system` exists, type `bool`, `nullable=False`,
   `server_default=sa.false()`. Default value on Python construction is
   `False`.
2. **Migration upgrade.**
   - Adds the `is_system` column on `recipe_books`.
   - Inserts exactly one `Trying Out` book per existing user that does
     not already own a system book — verified by tests + `alembic check`.
   - Inserts the matching `recipe_book_users` owner row for each new
     book.
   - Does NOT modify `users.default_recipe_book_id` or any other column
     on existing rows.
3. **Migration downgrade.** Drops the `is_system` column. (Books are not
   deleted — documented above.)
4. **Idempotency.** Running the back-fill twice (simulated in test by
   calling its core SQL twice) inserts no duplicates.
5. **`alembic check` clean.** `nx run migrator:check-models` passes —
   model + migration in lockstep.
6. **List endpoint.** `GET /v1/recipe-books` rows now include
   `is_system: bool`. Existing `recipe_count`, `user_role`, etc.,
   unchanged.
7. **Get endpoint.** `GET /v1/recipe-books/{id}` response gains
   `is_system: bool`.
8. **Update guard.** `PUT /v1/recipe-books/{id}` on a system book
   returns 400 with `INVALID_REQUEST`. Owner permission check still runs
   first (so a non-owner gets 403 even on a system book — consistent
   with the existing access-denied path).
9. **Delete guard.** `DELETE /v1/recipe-books/{id}` on a system book
   returns 400 with `INVALID_REQUEST`. Same access-check ordering as #8.
10. **Archive guard.** `POST /v1/recipe-books/{id}/archive` on a system
    book returns 400 with `INVALID_REQUEST`. Same ordering as #8.
11. **Create guard.** `POST /v1/recipe-books` ignores any
    client-supplied `is_system` field; the resulting row has
    `is_system=False`.
12. **Coverage.** 100% line coverage on touched API code, including the
    three guard branches. No `# pragma: no cover` allowed except where
    the existing convention permits.
13. **Lint.** `nx run api:lint`, `nx run migrator:lint`, `nx run
    utils:lint` all pass.
14. **Tests.** `nx run api:test`, `nx run utils:test` all pass.
15. **Sprint-status flipped** `recipe-defaults-1-...: backlog → done`.

## Tests added

### `services/api/tests/test_recipe_book.py`

| # | Test | Asserts |
|---|---|---|
| T1 | `test_list_recipe_books_includes_is_system` | A list with one system + one user book returns `is_system=true` and `false` respectively in the right rows. |
| T2 | `test_get_recipe_book_includes_is_system` | Single-book endpoint returns `is_system` in the response body. |
| T3 | `test_update_recipe_book_rejects_system_book` | 400 + `INVALID_REQUEST` when target book is system. |
| T4 | `test_delete_recipe_book_rejects_system_book` | 400 + `INVALID_REQUEST` when target book is system. |
| T5 | `test_archive_recipe_book_rejects_system_book` | 400 + `INVALID_REQUEST` when target book is system. |
| T6 | `test_create_recipe_book_ignores_is_system_param` | Posting `{"name": "X", "is_system": true}` results in a book with `is_system=False`. |

Mock fixtures (`MockRecipeBook`) gain `is_system: False` default — only
the tests that need a system book set it explicitly via
`MockRecipeBook(is_system=True)`.

## Risks & mitigations

- **Risk:** existing `MockRecipeBook` test rows, having lacked
  `is_system`, were silently relied on by other tests via attribute
  access (`book.is_system` → `AttributeError`). Now that the response
  includes `is_system`, any tests reaching into the model attribute will
  start working and any depending on the field's *absence* will break.
  **Mitigation:** add the default to `MockRecipeBook` so all existing
  callsites pick up `False` automatically. No callsites assert absence.

- **Risk:** the back-fill races with a concurrent user-creation flow.
  **Mitigation:** the migration runs in a single outer transaction; new
  user inserts since the migration began either appear in the SELECT
  (and get a Trying Out book) or appear after (and get one via story
  2's hook on next request). No race window where a user is left
  without a book.

- **Risk:** migration is run on a DB where `Trying Out` already exists
  as a user-created (non-system) book. **Mitigation:** the seed query
  filters by `is_system=true`. A user-named book with the same name is
  unaffected; the seeded system book sits alongside it. The Flutter
  switcher (story 3) sorts by `is_system DESC` so the system one shows
  up in the System section regardless.

- **Risk:** existing tests for `PUT/DELETE/POST archive` were structured
  on the *non-system* path; adding the guard could shift control flow
  in ways that flips an unrelated branch's coverage. **Mitigation:** the
  guard goes after the access check (which is what users hit first
  anyway), so non-system tests stay valid. Coverage gates re-run on
  each story.

## Definition of done

- [ ] Model + migration shipped; `alembic check` green.
- [ ] All four endpoint surfaces (`list`, `get`, `update`, `delete`,
      `archive`) emit `is_system` or guard against it as documented.
- [ ] All 6 new tests pass; existing tests stay green.
- [ ] `nx run api:lint`, `nx run migrator:lint`, `nx run utils:lint`,
      `nx run api:test`, `nx run utils:test` all green.
- [ ] `nx run migrator:check-models` green.
- [ ] Sprint-status flipped `backlog → done`.
- [ ] QA walkthrough file present.
- [ ] Atomic commit — no unrelated file-list entries.
