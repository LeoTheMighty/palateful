# recipe-defaults-2 — Backend: new-user provisioning hook seeds Trying Out + sets default

**Epic:** `epic-recipe-default-books`
**Status:** review
**Order in epic:** 2 of 4 (after `recipe-defaults-1`)

## Why

Story 1 landed the `is_system` column + a one-time back-fill of
`Trying Out` for every existing user. That covers the historical
population. New users — who land via the Auth0 callback path
(`get_current_user` / `get_current_user_async`) — currently get a
`recipe_books` row of their own only when they finish onboarding (see
`complete_onboarding.py`'s "My Recipes" bootstrap), and even then
their `default_recipe_book_id` is set to "My Recipes" rather than the
opinionated system book that the rest of this epic, plus follow-on
epics (`epic-recipe-list-organization`, `epic-recipe-bulk-organize`,
`epic-import-duplicate-detection`), all assume.

This story:

1. Adds `_ensure_system_trying_out` (sync) and
   `_ensure_system_trying_out_async` (async) helpers in
   `services/api/src/dependencies.py`. They mirror the existing
   `_ensure_default_calendar` pattern: idempotent SELECT-before-INSERT
   inside a SAVEPOINT.
2. Wires both into `get_current_user` and `get_current_user_async` so
   every authed request's first hit on a brand-new auth0_id ends with
   the user owning a `Trying Out` system book and having
   `default_recipe_book_id` set.
3. Modifies `complete_onboarding.py` so it only sets
   `default_recipe_book_id` when the user does not already have one —
   keeps Trying Out as the share-import default for new users while
   still creating the user-facing "My Recipes" book.

After this lands, sharing a recipe in / pasting a URL / dropping a
photo as a brand-new user routes the result into Trying Out without
the user ever seeing a "pick a destination" dialog.

## Scope — files this story touches

**MODIFY**
- `services/api/src/dependencies.py` — add two helpers
  (`_ensure_system_trying_out`, `_ensure_system_trying_out_async`) +
  call them from `get_current_user` / `get_current_user_async` after
  `find_or_create_by` + `_finalize_auth`.
- `services/api/src/api/v1/user/complete_onboarding.py` — only set
  `user.default_recipe_book_id` when it's currently None.
- `services/api/tests/test_dependencies.py` — sync helper tests.
- `services/api/tests/test_async_auth_deps.py` — async helper tests.
- `services/api/tests/test_user.py` — onboarding test that asserts
  default is preserved when already set.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  `recipe-defaults-2-...: backlog → done`.

**NEW**
- `_bmad-output/implementation-artifacts/recipe-defaults-2-backend-new-user-provisioning-hook-seeds-trying-out-and-default.md` (this file).
- `_bmad-output/implementation-artifacts/recipe-defaults-2-backend-new-user-provisioning-hook-seeds-trying-out-and-default-qa-walkthrough.md` (QA checklist).

### Out of scope — deliberate deferrals

- **`complete_onboarding.py`'s "My Recipes" book is preserved.** The
  epic locks Trying Out as the share-import default but does not
  remove the "My Recipes" book from onboarding. Users still get a
  user-facing personal book they can rename / delete via the existing
  long-press menu. The only behaviour change in onboarding is the
  conditional default-set — for new users post-defaults-2, the default
  stays Trying Out (set by the auth callback) instead of getting
  overwritten by "My Recipes".
- **No retroactive default-set.** Story 4 audits the share-import
  flow on the Flutter side. Users who were back-filled with a Trying
  Out book by story 1 but who have a NULL `default_recipe_book_id` get
  picked up here too — the auth-callback hook runs on every request
  and is a no-op for users who already own a system book except for
  the default-set step (which is itself guarded).
- **No new endpoint.** Provisioning happens server-side; the client
  observes only the resulting state via `GET /v1/users/me` +
  `GET /v1/recipe-books`.

## Helper contract

```python
def _ensure_system_trying_out(database: Database, user: User) -> RecipeBook | None:
    """Ensure `user` owns a non-archived system recipe book named
    Trying Out, set their default to it if currently None.

    Mirrors `_ensure_default_calendar`:
      - SELECT for an active system book (is_system=true,
        archived_at IS NULL) owned by `user`.
      - On miss: INSERT inside a `begin_nested()` SAVEPOINT — book
        row + RecipeBookUser('owner') membership row.
      - On IntegrityError (concurrent provisioning won the race),
        re-read and return the winner's book.
      - If `user.default_recipe_book_id` is None after the call, set
        it to the system book's id. Never overwrites an existing
        default.

    Idempotent: re-calling for a user who already owns a system book
    returns the existing one. Default-set is a one-time write
    (skipped if already set).
    """
```

Async sibling: `_ensure_system_trying_out_async(database: AsyncDatabase, user: User)`.

## Wiring

```python
# services/api/src/dependencies.py — get_current_user
user = database.find_or_create_by(User, auth0_id=auth0_id, defaults={...})
user = _finalize_auth(database, user, claims)
_ensure_default_calendar(database, user)
_ensure_system_trying_out(database, user)   # NEW
return user
```

Same one-line addition in `get_current_user_async` after
`_ensure_default_calendar_async`.

## Onboarding change

```python
# services/api/src/api/v1/user/complete_onboarding.py — was:
user.default_recipe_book_id = recipe_book.id

# now:
if user.default_recipe_book_id is None:
    user.default_recipe_book_id = recipe_book.id
```

The `if` keeps existing behaviour for users that somehow hit
onboarding without the auth-callback hook having fired (test envs,
direct DB fixtures). For real new users, the auth callback runs first
and sets the default to Trying Out; onboarding leaves it alone.

## Acceptance criteria

1. **Sync helper exists.** `_ensure_system_trying_out` in
   `dependencies.py` matches the contract above.
2. **Async helper exists.** `_ensure_system_trying_out_async` in
   `dependencies.py` matches the contract above.
3. **Sync wiring.** `get_current_user` calls
   `_ensure_system_trying_out` after `_ensure_default_calendar`.
4. **Async wiring.** `get_current_user_async` calls
   `_ensure_system_trying_out_async` after
   `_ensure_default_calendar_async`.
5. **Idempotency (sync).** Calling the helper twice for a user who
   already owns a system book returns the existing book; no second
   insert; default-set is skipped if already set.
6. **Idempotency (async).** Same as #5 for the async helper.
7. **Default-set semantics.** When the user has
   `default_recipe_book_id=None` and a freshly-created system book,
   the helper sets the default. When the user already has a default,
   the helper leaves it alone.
8. **Race safety (sync + async).** SAVEPOINT-wrapped INSERT; on
   IntegrityError the helper re-reads and returns the concurrent
   winner's book.
9. **Onboarding does not override existing default.** A user who hits
   `complete_onboarding` with a non-null `default_recipe_book_id`
   ends up with that same default after onboarding, not the new
   "My Recipes" book.
10. **Onboarding still sets default for users with NULL default.**
    Backwards-compatible: a user who somehow reaches onboarding with
    `default_recipe_book_id=None` (test fixtures, direct-DB users)
    still gets it set to the "My Recipes" book.
11. **Coverage.** 100% line coverage on touched files.
12. **Lint + tests.** `nx run api:lint`, `nx run api:test`,
    `nx run utils:lint`, `nx run utils:test`,
    `nx run migrator:check-models` all pass.
13. **Sprint-status flipped** `recipe-defaults-2-...: backlog → done`.

## Tests added

### `services/api/tests/test_dependencies.py`

| # | Test | Asserts |
|---|---|---|
| S1 | `test_ensure_system_trying_out_returns_existing` | Fast path — user already owns a system book; helper returns it; no INSERT. |
| S2 | `test_ensure_system_trying_out_creates_when_missing` | Happy creation — book + membership added inside SAVEPOINT; flush called. |
| S3 | `test_ensure_system_trying_out_sets_default_when_null` | After creation, when user has `default_recipe_book_id=None`, helper sets it to the new book's id. |
| S4 | `test_ensure_system_trying_out_preserves_existing_default` | After creation (or fast-path), when the user already has a non-null `default_recipe_book_id`, the helper leaves it alone. |
| S5 | `test_ensure_system_trying_out_handles_race_loss` | IntegrityError on the inner INSERT → caught; helper re-reads and returns the winner's book. |

### `services/api/tests/test_async_auth_deps.py`

| # | Test | Asserts |
|---|---|---|
| A1 | `test_ensure_system_trying_out_async_returns_existing` | sibling of S1 |
| A2 | `test_ensure_system_trying_out_async_creates_when_missing` | sibling of S2 |
| A3 | `test_ensure_system_trying_out_async_sets_default_when_null` | sibling of S3 |
| A4 | `test_ensure_system_trying_out_async_preserves_existing_default` | sibling of S4 |
| A5 | `test_ensure_system_trying_out_async_handles_race_loss` | sibling of S5 |

### `services/api/tests/test_user.py`

| # | Test | Asserts |
|---|---|---|
| U1 | `test_complete_onboarding_preserves_existing_default_recipe_book_id` | New user with `default_recipe_book_id` already set (story 2's auth callback ran) — onboarding does NOT overwrite it. The "My Recipes" book is still created and still appears in the response, but `mock_user.default_recipe_book_id` is unchanged. |

## Risks & mitigations

- **Risk:** the helper runs on every authed request; even at the
  fast-path it issues one extra SELECT per request. **Mitigation:**
  the SELECT is index-scoped on `recipe_book_users(user_id, ...)` —
  millisecond-class. FastAPI's `Depends` cache dedupes the helper
  call within a request (per the existing `pbq-8` spike test in
  `test_dependencies.py`). Total cost is negligible on the request
  budget.

- **Risk:** the existing `_ensure_default_calendar` already issues a
  similar query — total adds two SELECTs to every request. Negligible.

- **Risk:** test `test_complete_onboarding_success` asserts the
  "My Recipes" name in the response. With our conditional default-set,
  a user with `default_recipe_book_id=None` still gets it set; the
  response shape does not change. **Mitigation:** existing test stays
  green; we only add a new test for the preserved-default case.

- **Risk:** the auth-callback hook fires in unexpected places (admin
  scripts, websocket re-auth). **Mitigation:** the helper is fully
  idempotent — no-op when the user already owns a system book.

## Definition of done

- [ ] Both helpers shipped + wired.
- [ ] Onboarding's default-set is conditional.
- [ ] All 11 new tests (S1–S5, A1–A5, U1) pass.
- [ ] Lint + tests + check-models all green.
- [ ] Sprint-status flipped `backlog → done`.
- [ ] QA walkthrough file present.
- [ ] Atomic commit.
