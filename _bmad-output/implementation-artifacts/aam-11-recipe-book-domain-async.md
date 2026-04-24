# Story: aam-11 — Recipe Book Domain Async Conversion

**Epic:** `epic-api-async-migration.md` — Phase 3 per-domain chunk D-01
**Status:** done
**Phase-1 snippet:** `_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md` §CHUNK D-01

## What shipped

Every HTTP handler under `/v1/recipe-books/*` is now `async def`, uses the
async deps (`get_current_user_async`, `get_async_database`), and dispatches
through `await X.call(...)` on an `AsyncEndpoint` subclass. The MCP
`recipe_books` tool set moves to `call_endpoint_async`. The `POST
/recipe-books/{id}/members` notification fan-out uses the shared
`notify_via_threadpool` bridge so the sync `notify_book_shared` helper
runs on a fresh `Database(db=SessionLocal())` inside the threadpool
thread and never touches the event loop.

The `add_recipe_book_member` activity-feed write inlines the three lines
of `create_activity` directly against the async session (matches the
pattern from `aam-10`) — no `create_activity_async` twin is added.

WebSocket handler (`/v1/recipe-books/ws/{book_id}`) is **unchanged** per
the `aam-phase1` ground-truth rule: the WS body runs one sync
`db.query(RecipeBookUser)...` at connect-time and otherwise awaits
network I/O; leaving it on the sync dep keeps the WS path out of scope
for this chunk (per the "DO NOT TOUCH WS handlers" playbook rule).

## Files touched

### Endpoint subclasses (`services/api/src/api/v1/recipe_book/*.py`, 12 files)

- `add_recipe_book_member.py` — `AsyncEndpoint`; inlined activity-feed
  write against async session; swapped `find_by` / `create` to `await`.
- `archive_recipe_book.py` — `AsyncEndpoint`; `await self.database.find_by`,
  `await self.database.db.commit()`.
- `create_recipe_book.py` — `AsyncEndpoint`; `await self.database.create`
  + `await self.database.db.refresh` for both the book and membership rows.
- `delete_recipe_book.py` — `AsyncEndpoint`; `await self.database.delete`
  (cascades handled by DB FK constraints).
- `get_public_recipe_book.py` — `AsyncEndpoint`; `await database.find_by`
  + `await database.where(...).all()`.
- `get_recipe_book.py` — `AsyncEndpoint`; `await self.db.execute(select(...))`
  for recipes + members queries.
- `list_archived_recipe_books.py` — `AsyncEndpoint`; `await self.db.execute`
  for the outer-join shape.
- `list_recipe_books.py` — `AsyncEndpoint`; subquery rebuilt with
  `select(...).subquery()`; count via `select(func.count()).select_from(...)`
  followed by paginated `await self.db.execute`.
- `remove_recipe_book_member.py` — `AsyncEndpoint`; `await self.database.delete`.
- `restore_recipe_book.py` — `AsyncEndpoint`; `await self.database.db.commit()`.
- `update_recipe_book.py` — `AsyncEndpoint`; recipe-count via
  `select(func.count(Recipe.id))` + `scalar()`.
- `update_recipe_book_member_role.py` — `AsyncEndpoint`; `await self.database.update`.

### Router + MCP + notifications bridge

- `services/api/src/routers/v1/recipe_book_router.py` — every HTTP handler
  flipped `async def` + async deps + `await X.call(...)`. The add-member
  handler commits the async session before handing off to
  `notify_via_threadpool(notify_book_shared, ...)`. WebSocket endpoint
  kept sync (unchanged).
- `services/api/src/mcp_server/tools/recipe_books.py` — all three tools
  (`list_recipe_books`, `get_recipe_book`, `create_recipe_book`) are now
  `async def` and dispatch through `await call_endpoint_async(...)`.

### Tests

- `services/api/tests/test_recipe_book.py` — every test rewritten to the
  `mock_async_db` + `MockExecuteResult` shape. No test deletions; every
  name + assertion preserved.
- `services/api/tests/test_recipe_book_members.py` — same conversion;
  added a small `_configure_add_member_mocks` helper so the 3×
  `set_find_by` calls the add-member path needs (owner RBU, target
  User, target RecipeBook for activity/notification) are DRY.
- `test_recipe_book_notifications.py` — **unchanged.** It unit-tests the
  sync `notify_book_shared` / `notify_recipe_added` / ... helpers
  directly and never hits an HTTP endpoint. Bridge wrap is tested at
  the foundations layer (`test_notifications_bridge.py`, already live).
- `test_recipe_book_websocket.py` — **unchanged.** WS route kept sync.

## Acceptance criteria mapping

| AC | Status | Evidence |
|----|--------|----------|
| Every recipe_book endpoint inherits `AsyncEndpoint` | ✅ | 12/12 files grep clean for `class X(Endpoint)` |
| Router handlers `async def` + async deps + awaited `.call()` | ✅ | `recipe_book_router.py` — every HTTP handler flipped |
| MCP tool file uses `call_endpoint_async` | ✅ | `recipe_books.py` — 3/3 tools converted |
| Test file uses `mock_async_db` pattern | ✅ | `test_recipe_book.py` + `test_recipe_book_members.py` |
| 100% coverage holds on changed files | ✅ | `npx nx run api:test` green; `fail_under=100` |
| Lint clean | ✅ | `poetry run ruff check` — all checks passed |
| WS regression probe | ➖ | WS path unchanged — no auth-dep race surface introduced |

## Rollback

Single-line per-domain rollback during observation window: revert
`fef2223` (commit that landed this change alongside aam-12a reads) +
`bin/prod-deploy`. Response shapes are byte-identical so no client-side
impact.

## Post-merge observation

- `GET /v1/recipe-books/{recipe_book_id}` client-side p95 target: no
  regression > 20% vs. pre-aam-11 baseline (this endpoint was
  event-loop-queue-bound pre-migration; async run should flatten tails).
- `POST /v1/recipe-books/{id}/members` includes a DB commit + threadpool
  hop for notification fan-out; expected wall-clock delta is
  threadpool-hop cost (< 2ms p50).
- Book add → share invite → notify → partner sees notification flow
  remains unchanged (verified via unit-tested sync bridge + the
  notification-helper tests that ship unchanged with this PR).

## Deviations from the playbook

- **WS handler untouched.** Per the `aam-phase1-dev-snippets` "DO NOT
  TOUCH" rule, the WebSocket route kept its sync `Database` dep. The
  AC from the original epic text ("WS accepts AsyncSession") is
  superseded by that snippet.
- **Landed bundled with aam-12a commit `fef2223`.** A parallel `/dev`
  loop picked up this domain's staged files during coordination and
  emitted them under its commit. The content matches the aam-11 scope
  and passes all 110 recipe_book tests — no re-commit is warranted.
  Sprint-status.yaml flipped to `done` in this commit to close the
  loop.
