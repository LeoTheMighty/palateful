# aam-19 — User Profile + Push Tokens Domain Async

**Epic:** [epic-api-async-migration](../planning-artifacts/epic-api-async-migration.md)
**Status:** review
**Prerequisites landed:** aam-1..aam-6 (foundations), aam-foundations-notify-threadpool-helper, aam-10 (meal reference), aam-21 (notification-preferences + client-errors + feedback already async).

## Scope

Convert the remaining sync handlers in the user domain from `Endpoint` to
`AsyncEndpoint`. aam-21 already flipped `record_client_error`,
`get_notification_preferences`, `update_notification_preferences`, and
`create_user_feedback`. This story closes out the other 11 handlers
(profile, defaults, onboarding, push-tokens, username, export, search).

**Files in scope:**
- Router: `services/api/src/routers/v1/user_router.py` (11 sync handlers flipped to `async def`)
- Endpoints (`services/api/src/api/v1/user/`):
  - `get_me.py` — `GetMe`
  - `update_me.py` — `UpdateMe`
  - `set_default_recipe_book.py` — `SetDefaultRecipeBook`
  - `set_default_shopping_list.py` — `SetDefaultShoppingList`
  - `complete_onboarding.py` — `CompleteOnboarding` (calls sync `ensure_default_shopping_list` via threadpool)
  - `push_tokens.py` — `RegisterPushToken`, `UnregisterPushToken` (`GetNotificationPreferences` / `UpdateNotificationPreferences` already async from aam-21)
  - `set_username.py` — `SetUsername`
  - `check_username.py` — `CheckUsername`
  - `export_recipes.py` — `ExportRecipes`
  - `search_users.py` — `SearchUsers`
- Tests: `services/api/tests/test_user.py` rewritten to the `mock_async_db` pattern for every class except `TestRecordClientError` (already async from aam-21).

**Explicitly NOT in scope:**
- MCP tool at `services/api/src/mcp_server/tools/user.py` (`get_profile`) — reads
  `get_current_user()` directly without wrapping an `Endpoint`; nothing to convert.
- `services/api/src/api/v1/user/create_user_feedback.py` — already `AsyncEndpoint` (aam-21).
- `services/api/src/api/v1/user/record_client_error.py` — already `AsyncEndpoint` (aam-21).
- `services/api/src/api/v1/shopping_list/bootstrap.py` — stays sync; called by migration backfill + `CreateShoppingList` (aam-13 scope). `complete_onboarding` invokes it via `run_in_threadpool` on a fresh sync session.

## Approach

### Endpoint conversion — standard recipe

Each endpoint flips `Endpoint` → `AsyncEndpoint`, `def execute` →
`async def execute`, sync queries → `select()` + `await`. Direct
`self.db.query(...).filter(...).first()` translates to
`(await self.db.execute(select(X).where(...).limit(1))).scalars().first()`
per the cheat-sheet in `aam-phase1-dev-snippets.md`.

### Writes that mutate `self.user`

`update_me`, `set_default_recipe_book`, `set_default_shopping_list`,
`complete_onboarding`, `set_username`, `register_push_token`,
`unregister_push_token` all mutate the user object and commit. The
user returned by `get_current_user_async` is attached to the async
session, so plain attribute assignment + `await self.database.db.commit()`
replicates the sync path exactly.

`self.db.refresh(user)` becomes `await self.db.refresh(user)`.

### `complete_onboarding` — sync-helper fanout

`ensure_default_shopping_list(user, db)` is a sync helper shared with
the migration backfill sweep and `CreateShoppingList` (still sync in
aam-13). Rather than adding an `_async` twin just for onboarding, the
async `CompleteOnboarding` dispatches the post-commit bootstrap onto
the FastAPI threadpool with a fresh sync `Database(db=SessionLocal())`.
The sync block re-fetches the User by id (async session objects are
not safe to hand across threads) and calls the helper. Failures are
logged and swallowed, matching the sync behaviour.

### Router flip

All 11 handlers flip to `async def` + `Depends(get_current_user_async)`
+ `Depends(get_async_database)` + `return await X.call(...)`. Two
handlers that still exist as already-async (aam-21) stay untouched.
The obsolete sync imports (`get_current_user`, `get_database`, sync
`Database`) are dropped from the router once every handler uses the
async deps.

### Tests

`services/api/tests/test_user.py` rewritten top-to-bottom to the
`mock_async_db` pattern for every class except `TestRecordClientError`
(already async from aam-21):
- `mock_db.db.execute.return_value = MockExecuteResult(...)` →
  `mock_async_db.db.execute.side_effect = [MockExecuteResult(items=[...]), ...]`
- `mock_db.db.query.return_value = MockQuery([...])` → add a
  `MockExecuteResult(items=[...])` to the side_effect list (because the
  query has been rewritten as `await db.execute(select(...))`)
- `mock_db.set_find_by(Model, obj, ...)` → `mock_async_db.set_find_by(...)`
- All test names + assertions preserved; no deletions.

## Acceptance Criteria

- [x] All 11 user endpoints inherit `AsyncEndpoint`, `async def execute`, queries use `select()` + `await`
- [x] Router handlers are `async def` with `get_current_user_async` + `get_async_database`
- [x] `complete_onboarding` post-commit bootstrap dispatched via `run_in_threadpool`; re-fetches User in sync session
- [x] `test_user.py` rewritten to `mock_async_db` shape; every test name preserved; no tests deleted
- [x] `npx nx run api:lint` green
- [x] `npx nx run api:test -- tests/test_user.py` green
- [x] No sync DB call on the event loop inside any user handler (visual audit)

## Gotchas

- **Push-token duplicate-list branch.** `RegisterPushToken` skips the commit when
  the token is already present. Keep the `if params.token not in tokens:` guard —
  skipping an unnecessary commit is a perf win, not dead code.
- **`set_default_recipe_book` membership query.** Uses `db.query(...).filter(...)`
  to look up `RecipeBookUser`. Converts to `await db.execute(select(RecipeBookUser).where(...)...limit(1))`.
  Tests were hitting `mock_db.db.query.return_value` — must become a
  `mock_async_db.db.execute.side_effect` entry.
- **`ExportRecipes` walks many tables.** Translation is straightforward but
  the side_effect list for the "happy path" test is long (memberships + per-book
  recipes + per-recipe steps + ingredients + notes + versions). Easier: use
  `mock_async_db.set_where(...)` for the homogeneous `where(Model, ...)` calls and
  side_effect for the one explicit `select(RecipeIngredient, Ingredient).join(...)`.
- **Parallel-session hazard.** Local `main` has WIP from /dev aam-12a, aam-13,
  aam-17, aam-15 (unpushed). `nx run api:test` may show failures outside this
  domain; the aam-19 gate is "test_user.py passes" + "no new failures in
  previously-passing user-domain tests." Stage file-by-file on commit.

## Push status

Local `main` is ahead of `origin/main`. This story commits atomically;
push is deferred to end-of-run when parallel loops converge.
