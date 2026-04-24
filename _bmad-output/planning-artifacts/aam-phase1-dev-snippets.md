<!-- plain refactor playbook, no party-mode, no PRD synthesis — ground truth for parallel /dev agents -->

# aam-* Async Migration — Phase 1 & 2 Dev Snippets

**Ground truth as of 2026-04-24.** Phase 0 emergency patch landed on `main` (commit `2243928`): 150 router handlers flipped from `async def` (with sync body → blocked event loop) to `def` (runs in FastAPI threadpool → loop stays free). The user-facing outage is over. This playbook completes the migration the right way and then cleans up.

This doc is **action-oriented**. Each chunk below is a self-contained `/dev` snippet that a fresh session-scoped agent can execute without reading the rest. Foundations ships serially first; then 13 domain chunks run in **parallel**; then the cleanup chunks finish it.

---

## Current state — what's already in place

- `AsyncEndpoint` base class — `libraries/utils/utils/api/endpoint.py:336-454`
- `AsyncDatabase` + `AsyncQuery` — `libraries/utils/utils/services/async_database.py`
- `get_async_database`, `get_current_user_async` — `services/api/src/dependencies.py:66-83, 241-303`
- Async engine + pool wired — `libraries/utils/utils/services/database.py` (DB_ASYNC_POOL_SIZE=20/40)
- RDS `max_connections` bumped to 100 (aam-1)
- Error-log write via `run_in_threadpool` onto the dedicated `error_log_engine` sub-pool (aam-3)
- `count_queries` test helper back-compat (aam-4)
- `call_endpoint_async` + MCP contextvar for async DB (aam-3)
- Reference implementations:
  - **Endpoint:** `services/api/src/api/v1/meal/get_meal.py`, `list_meals.py`
  - **Router:** `services/api/src/routers/v1/meal_router.py`
  - **MCP tool:** `services/api/src/mcp_server/tools/meals.py`
  - **Test:** `services/api/tests/test_meal_router.py` (async mock shape)

---

## The conversion recipe (every domain chunk follows this)

### 1. Endpoint class: `Endpoint` → `AsyncEndpoint`

**Before (sync):**
```python
from utils.api.endpoint import Endpoint, success

class GetRecipeBook(Endpoint):
    def execute(self, recipe_book_id: str):
        user: User = self.user
        membership = self.database.find_by(RecipeBookUser, user_id=user.id, recipe_book_id=recipe_book_id)
        if not membership:
            raise APIException(403, "...", code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED)
        recipe_book = self.database.find_by(RecipeBook, id=recipe_book_id)
        recipes = self.db.query(Recipe).filter(Recipe.recipe_book_id == recipe_book_id).all()
        return success(data=...)
```

**After (async):**
```python
from sqlalchemy import select
from utils.api.endpoint import AsyncEndpoint, success

class GetRecipeBook(AsyncEndpoint):
    async def execute(self, recipe_book_id: str):
        user: User = self.user
        membership = await self.database.find_by(RecipeBookUser, user_id=user.id, recipe_book_id=recipe_book_id)
        if not membership:
            raise APIException(403, "...", code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED)
        recipe_book = await self.database.find_by(RecipeBook, id=recipe_book_id)
        recipes_result = await self.db.execute(
            select(Recipe).where(Recipe.recipe_book_id == recipe_book_id)
        )
        recipes = list(recipes_result.scalars().all())
        return success(data=...)
```

**Query translation cheat-sheet:**

| sync `self.db.query(X)...` | async `await self.db.execute(select(X)...)` |
|---|---|
| `.query(X).filter(Y).all()` | `(await db.execute(select(X).where(Y))).scalars().all()` |
| `.query(X).filter(Y).first()` | `(await db.execute(select(X).where(Y).limit(1))).scalars().first()` |
| `.query(X).filter(Y).count()` | `int((await db.execute(select(func.count()).select_from(X).where(Y))).scalar_one())` |
| `.query(func.count(X.id)).scalar()` | `(await db.execute(select(func.count(X.id)))).scalar_one()` |
| `.query(X).outerjoin(Y, cond)` | `select(X).outerjoin(Y, cond)` |
| `.query(X, Y).join(Z)` | `select(X, Y).join(Z)` — then iterate `result.all()` for tuple rows |
| `self.database.find_by(X, k=v)` | `await self.database.find_by(X, k=v)` |
| `self.database.where(X, ...).all()` | `await self.database.where(X, ...).all()` — `where()` returns `AsyncQuery` sync, `.all()`/`.first()` are async |
| `self.database.create(m)` | `await self.database.create(m)` |
| `self.database.update(m, **kw)` | `await self.database.update(m, **kw)` |
| `self.database.delete(m)` | `await self.database.delete(m)` |
| `self.database.db.flush()` | `await self.database.db.flush()` |
| `self.database.db.commit()` | `await self.database.db.commit()` |
| `with self.database.db.begin_nested():` | `async with self.database.db.begin_nested():` |
| `session.begin_nested()` IntegrityError pattern | identical shape, just `async with`, `await IntegrityError catch` |

### 2. Router handler: sync `def` → `async def` + async deps

**Before (Phase 0 state):**
```python
@router.get("/{id}")
def get_recipe_book(
    id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    return GetRecipeBook.call(recipe_book_id=id, user=user, database=database)
```

**After:**
```python
@router.get("/{id}")
async def get_recipe_book(
    id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    return await GetRecipeBook.call(recipe_book_id=id, user=user, database=database)
```

### 3. Notification / sync-service escape hatch (when an async handler calls a sync helper that takes a sync `Database`)

Sync helpers (`notifications.py`, `activity_service.create_activity`, `push_notification`, boto3/AWSService) stay sync for now. Call them from async via `run_in_threadpool`, bound to a fresh short-lived sync session:

```python
from fastapi.concurrency import run_in_threadpool
from utils.services.database import Database, SessionLocal

async def execute(self, ...):
    # ... async DB work ...
    await self.database.commit()   # commit async state BEFORE sync fan-out

    # Sync fan-out (notifications / activity / AWS presign / etc.):
    def _sync_side_effect():
        sync_db = Database(db=SessionLocal())
        try:
            notify_book_shared(
                recipe_book_id=str(book.id),
                recipe_book_name=book.name,
                invited_user=target_user_snapshot,
                invited_by=user_snapshot,
                database=sync_db,
            )
        finally:
            sync_db.close()
    await run_in_threadpool(_sync_side_effect)
```

**Pass snapshots (dict or detached ORM with loaded attrs), not async ORM instances**, across the threadpool boundary — the sync session doesn't share state with the async one. For the simple case where only IDs are needed, re-fetch in the sync session.

**Activity creation (3 callsites — keep sync, inline in async execute):**
```python
# Inline the 3 lines from utils.services.activity_service.create_activity since
# we don't want to grow a create_activity_async twin just for this. Uses the
# async session directly.
from utils.models.user_activity import UserActivity
activity = UserActivity(
    user_id=user.id,
    type="partner_action",
    title=f"{target_user.name} joined {book_name}",
    action_url=f"/recipe-books/{recipe_book_id}/members?role={caller_membership.role}",
)
self.db.add(activity)
await self.db.flush()
```

### 4. MCP tool: `call_endpoint` → `call_endpoint_async`

**Before:**
```python
from mcp_server.server import call_endpoint, mcp

@mcp.tool()
def get_recipe_book(book_id: str) -> str:
    return call_endpoint(GetRecipeBook, recipe_book_id=book_id)
```

**After:**
```python
from mcp_server.server import call_endpoint_async, mcp

@mcp.tool()
async def get_recipe_book(book_id: str) -> str:
    return await call_endpoint_async(GetRecipeBook, recipe_book_id=book_id)
```

### 5. Tests: sync `MockQuery` → async `MockExecuteResult`

**Before (sync pattern):**
```python
def test_get_recipe_book_success(self, client, mock_db, mock_user):
    mock_db.db.query.return_value = MockQuery([(book, 3, "owner", 1, datetime.now(UTC))])
    mock_db.set_find_by(RecipeBookUser, membership, user_id=..., recipe_book_id=...)
    response = client.get(f"/v1/recipe-books/{book_id}")
```

**After (async pattern — see `services/api/tests/test_meal_router.py` for full examples):**
```python
def test_get_recipe_book_success(self, client, mock_async_db, mock_user):
    # Each async db.execute() call consumes one entry in side_effect, in order.
    mock_async_db.db.execute.side_effect = [
        MockExecuteResult(items=[membership]),        # find_by RecipeBookUser
        MockExecuteResult(items=[book]),              # find_by RecipeBook
        MockExecuteResult(items=[recipe1, recipe2]),  # select(Recipe)
        MockExecuteResult(items=[(rbu1, user1)]),     # select(RBU, User) join
    ]
    response = client.get(f"/v1/recipe-books/{book_id}")
```

**Counting `db.execute` calls:** read the converted `execute` method top-to-bottom, count each `await self.db.execute(...)` and each `await self.database.find_by(...)` / `await self.database.where(...).all()` (each hits `db.execute` once under the hood). That's your `side_effect` length.

`client` fixture already injects `mock_async_db` because `get_async_database` + `get_current_user_async` are overridden in `conftest.py:client` (added in aam-10).

### 6. Done definition per domain chunk

- All domain endpoints inherit `AsyncEndpoint`, `async def execute`, queries use `select()` + `await`.
- Router handler = `async def`, uses `get_current_user_async` + `get_async_database`, returns `await X.call(...)`.
- MCP tool file converted to `call_endpoint_async` (where applicable).
- Test file converted to `mock_async_db` mock shape. All existing test names preserved; no test deletions.
- `npx nx run api:lint` passes.
- `npx nx run api:test -- <domain test file>` passes.
- Full CI green including 100% coverage gate.
- Sprint-status entry flips `backlog` → `done`.

---

## Foundations — must land before parallel domain work

Most foundations already landed (aam-1..aam-6, aam-10, aam-21). Two gaps remain:

### CHUNK-F1 — `notify_via_threadpool` helper (~1 hour)

**Slug:** `aam-foundations-notify-threadpool-helper`
**Serial gate:** yes — every domain that sends push must use this.
**Files:**
- `libraries/utils/utils/services/notifications_bridge.py` (new)
- `libraries/utils/utils/services/__init__.py` (export)
- `services/api/tests/test_notifications_bridge.py` (new)

Ship a single helper that every converted endpoint uses to invoke a sync notification helper from an async context. Contract:

```python
async def notify_via_threadpool(fn, /, *args, **kwargs) -> Any:
    """Run a sync notification helper on a fresh sync Database inside the threadpool.

    `fn` must accept `database: Database` (keyword). Caller passes the other args.
    Ensures the sync session is closed even if `fn` raises — errors are logged via
    ErrorReporter (service='push_notifications') and swallowed, matching the
    existing notification fire-and-forget contract.
    """
```

This replaces every domain's bespoke `def _sync_side_effect(): sync_db = Database(...); ...`. Tests: success path, exception path (session closed, error logged, no raise).

### CHUNK-F2 — `parser_router` + `import_router` boto3 threadpool wrap (~2 hours)

**Slug:** `aam-9-boto3-threadpool-wrap` (already in sprint-status as `backlog`)
**Serial gate:** no — this is independent of the domain conversions. Can run in parallel with F1 or with any domain chunk.
**Files:**
- `services/api/src/api/v1/import_job/start_import.py`
- `services/api/src/api/v1/import_job/get_upload_url.py`
- `services/api/src/api/v1/parser/submit_parser_job.py`
- `services/api/src/api/v1/parser/submit_batch_parser_job.py`
- `services/api/src/api/v1/parser/get_upload_url.py`
- Any other callsite of `AWSService.submit_batch_job` / `get_s3_object` / `presign` found by grep.

Pure `run_in_threadpool` wrap of the sync boto3 calls. No contract changes. Tests wrap mock calls with async-compatible mocks; existing tests stay.

---

## Domain chunks (all parallelizable after F1 lands)

Each is an existing `aam-NN-*` sprint-status story. Snippet templates below.

| # | Story ID | Router file | Endpoint dir | Test files | Notes |
|---|---|---|---|---|---|
| D-01 | aam-11 | recipe_book_router.py | recipe_book/ | test_recipe_book.py, test_recipe_book_members.py, test_recipe_book_notifications.py | notifications + activity creation |
| D-02a | aam-12a | recipe_router.py (11 read handlers) | recipe/ (reads + _response.py) | test_recipe.py (read classes), test_share_recipe.py | **split 2026-04-24** — reads + share + photo-upload-url + toggle_favorite. Converts `build_recipe_response` used downstream by 12b. |
| D-02b | aam-12b | recipe_router.py (13 write handlers) | recipe/ (writes) | test_recipe.py (write classes), test_fork_recipe.py, test_recipe_ingredient_input.py | **depends on 12a** — notifications (fork/note/added) via `notify_via_threadpool`. |
| D-03 | aam-13 | shopping_list_router.py | shopping_list/ | test_shopping_list*.py, test_check_off_items.py, test_add_meal_to_shopping_list.py | notifications + event-logger + WebSocket preserved |
| D-04 | aam-14 | calendar_router.py + meal_event_router.py | calendar/ + meal_event/ | test_calendar_*.py, test_meal_event*.py, test_add_meal_event_to_shopping_list.py | **two routers combined** per existing story |
| D-05 | aam-15 | pantry_router.py | pantry/ | test_pantry.py | smallest (5 endpoints) — good warmup |
| D-06 | aam-16 | activity_router.py | user_activity/ | test_user_activity*.py | no notifications, no writes to other domains |
| D-07 | aam-17 | search_router.py | search/ | test_search.py | 1 endpoint — smallest |
| D-08 | aam-18 | import_router.py | import_job/ | test_import_*.py | **20 endpoints.** `StartImport` also touched by F2 (boto3) — merge order note below |
| D-09 | aam-19 | user_router.py (11 remaining handlers — 4 already async from aam-21) | user/ | test_user*.py | push-token registration in scope |
| D-10 | aam-20 | admin_router.py | admin/ | test_admin*.py | 13 endpoints, 2 push-writes (SendTestPush, GetAdminPushHealth) |
| D-11 | **new aam-28** | friends_router.py | friends/ | test_friends.py | 8 endpoints — **not in existing epic; add to sprint-status as aam-28-friends-domain-async** |
| D-12 | **new aam-29** | parser_router.py | parser/ | test_parser*.py | 8 endpoints — external service (boto3, Batch). **Coordinate with F2**; parser should land AFTER F2 so parser chunk only does the endpoint→AsyncEndpoint conversion, not the boto3 wrapping |
| D-13 | **new aam-30** | recurrence_rule_router.py | recurrence_rule/ | test_recurrence_rule.py | 5 endpoints |

**Cross-chunk dependency notes:**
- D-11, D-12, D-13 are net-new chunks — add to `sprint-status.yaml` as part of the refactor PR. Story IDs reserved: `aam-28-friends-domain-async`, `aam-29-parser-domain-async`, `aam-30-recurrence-rule-domain-async`.
- D-08 (import) + CHUNK-F2 (boto3) overlap on `StartImport` / `get_upload_url`. Merge order: F2 lands first, then D-08. If D-08 opens before F2, rebase after F2.
- No two domain chunks edit the same file — safe to run in parallel.
- `sprint-status.yaml` races are expected per `project_parallel_dev_loops.md` — stage file-by-file on commit, not `git add -A`.

### /dev snippet template (parameterize `DOMAIN` + `STORY_ID` + `FILE_LIST`)

Copy-paste per chunk. Replace `<DOMAIN>`, `<STORY_ID>`, `<ROUTER>`, `<ENDPOINT_DIR>`, `<TESTS>`:

```
/dev <STORY_ID>

Convert the <DOMAIN> domain from sync Endpoint to async AsyncEndpoint. Phase 0 has
landed on main — router handlers are currently `def` running in the FastAPI
threadpool. This chunk flips them back to `async def` with async deps and awaited
.call(), and rewrites the endpoint classes to AsyncEndpoint.

REFERENCE IMPLEMENTATIONS (read these first, copy pattern exactly):
- Endpoint class: services/api/src/api/v1/meal/get_meal.py
- Router: services/api/src/routers/v1/meal_router.py
- MCP tool: services/api/src/mcp_server/tools/meals.py
- Async tests: services/api/tests/test_meal_router.py
- Recipe: _bmad-output/planning-artifacts/aam-phase1-dev-snippets.md (this doc)

SCOPE (touch only these files — coordinate via sprint-status, stage file-by-file):
- Router: services/api/src/routers/v1/<ROUTER>
- Endpoints: services/api/src/api/v1/<ENDPOINT_DIR>/*.py (every file with `class X(Endpoint)`)
- MCP tool: services/api/src/mcp_server/tools/<DOMAIN>.py (if exists)
- Tests: services/api/tests/<TESTS>

DO NOT TOUCH:
- WebSocket handlers (recipe_book_websocket, shopping_list_websocket) — already async.
- Any already-async handler (grep for `async def` + `await` in the router — skip those).
- Handlers in other domains.
- libraries/utils/utils/api/endpoint.py or async_database.py — foundations are done.

STEPS:
1. Read the reference implementations above.
2. For each endpoint class in <ENDPOINT_DIR>:
   a. Change base: `class X(Endpoint)` → `class X(AsyncEndpoint)`.
   b. `def execute` → `async def execute`.
   c. Translate every DB call per the cheat-sheet in aam-phase1-dev-snippets.md.
   d. If the endpoint calls a sync notification / activity helper, use
      `notify_via_threadpool` (see foundations CHUNK-F1) or inline the sync helper
      inside a `run_in_threadpool` block with a fresh `Database(db=SessionLocal())`.
      create_activity: inline the 3-line UserActivity creation directly in async.
3. Flip each router handler to:
   - `async def`
   - `Depends(get_current_user_async)` + `Depends(get_async_database)`
   - `return await X.call(...)`
4. Convert MCP tool (if present) to `call_endpoint_async` + `async def`.
5. Rewrite tests: replace `mock_db.db.query.return_value = MockQuery([...])` with
   `mock_async_db.db.execute.side_effect = [MockExecuteResult(items=[...]), ...]`.
   Count `await self.db.execute(...)` + `await self.database.find_by(...)` +
   `await self.database.where(...).all()` in each endpoint to size the
   side_effect list correctly. Preserve all test names + assertions.
6. Lint: `npx nx run api:lint`.
7. Test (scope): `npx nx run api:test -- services/api/tests/<TESTS>`.
8. Full test + coverage: `npx nx run api:test` — 100% coverage gate must pass.
9. Stage file-by-file (not `git add -A`) to avoid sprint-status races with parallel loops.
10. Commit, push, open PR. Title: `feat(api): <STORY_ID> — <DOMAIN> domain async`.

DEFINITION OF DONE:
- [ ] Every Endpoint subclass in <ENDPOINT_DIR> is AsyncEndpoint.
- [ ] Every router handler (excluding WS + already-async) is `async def` with async deps + awaited call.
- [ ] MCP tool uses `call_endpoint_async` (if file exists).
- [ ] Test file uses mock_async_db pattern. No tests deleted. 100% coverage.
- [ ] `nx run api:lint` green. `nx run api:test` green.
- [ ] sprint-status.yaml flipped <STORY_ID>: backlog → review (then Code Review agent flips to done).
- [ ] PR body cites pre/post `route_paint` p95 from client_latencies (per epic AC #9).
```

---

## Phase 2 — cleanup (after ALL Phase 1 domains land)

These are synchronization-point chunks. Don't start until every domain chunk in the table above is `done` in sprint-status.

### CHUNK-C1 — sync-in-async startup guard

**Slug:** `aam-25-sync-in-async-startup-guard` (already in sprint-status)
**Dependency:** every Phase 1 domain done.
**Files:**
- `services/api/src/main.py` (lifespan startup)
- `services/api/tests/test_sync_async_guard.py` (new)

On startup, enumerate open sessions by engine at the first request-handler dispatch. Fail fast if a sync `Session` opens anywhere outside the whitelisted paths (error-log writer, BatchedLatencyWriter, BatchedTaskWriter, BatchedClientLatencyWriter, unit-alias pre-warm, `manage.py`). Prevents future regressions.

### CHUNK-C2 — error-tracking middleware async

**Slug:** `aam-22-error-tracking-middleware-async`
**Files:**
- `services/api/src/middleware/error_tracking.py`
- `services/api/src/middleware/latency_capture.py`
- related tests

Middleware currently creates its own sync `Database` for error writes. Flip to `run_in_threadpool`-wrapped `Database(db=ErrorLogSessionLocal())` pattern (already how `AsyncEndpoint` does it).

### CHUNK-C3 — lifespan pre-warm

**Slug:** `aam-23-lifespan-and-pre-warm`
**Files:**
- `services/api/src/main.py`
- `services/api/tests/test_lifespan.py`

Mask asyncpg's first-query prepared-statement cache build (~100-300ms per connection) by running `SELECT 1` on every pool connection at startup before healthcheck flips green.

### CHUNK-C4 — cutover + shim removal

**Slug:** `aam-24-cutover-and-shim-removal` (the big one)
**Dependency:** C1 + C2 + C3 done AND 24h soak from last domain chunk.
**Files:**
- `libraries/utils/utils/api/endpoint.py` (delete `Endpoint` class — only `AsyncEndpoint` remains, renamed to `Endpoint`)
- `libraries/utils/utils/services/database.py` (`pool_size` 10→5, `max_overflow` 20→10; keep class for whitelisted paths + scripts + worker)
- `services/api/src/dependencies.py` (delete `get_current_user` + `get_database`; keep only async variants)
- `services/api/src/mcp_server/server.py` (delete sync `call_endpoint`)
- Every converted import (drop `get_current_user` / `get_database` imports wholesale)

Pure delete PR — no new behavior. Small but mechanical. Run `nx run api:lint` + `nx run api:test` to confirm nothing references removed symbols.

### CHUNK-C5 — OpenAI async swap

**Slug:** `aam-7-openai-async`
**Independent:** can run parallel with other Phase 2 chunks.
**Files:**
- Every callsite of `OpenAI(...)` client in `services/api/src/` → `AsyncOpenAI(...)`.
- Every `client.chat.completions.create(...)` → `await client.chat.completions.create(...)`.

### CHUNK-C6 — Firebase threadpool wrap (already partially done in aam-8 by the domain chunks via `notify_via_threadpool`)

**Slug:** `aam-8-firebase-threadpool-wrap`
**Verify:** grep for any remaining sync `messaging.send` call on the event loop; wrap in `run_in_threadpool`. Likely done if all domain chunks used `notify_via_threadpool`.

### CHUNK-C7 — latency baseline snapshot

**Slug:** `aam-26-latency-baseline-snapshot`
**Files:** `tools/` — add a baseline capture script that diffs pre- vs post-migration p95 from `client_latencies`.

### CHUNK-C8 — concurrent load integration test

**Slug:** `aam-27-concurrent-load-integration-test`
**Files:** `services/api/tests/test_concurrent_load.py` (new)

Integration test that fires 50 concurrent requests to `/v1/meals/{id}` + `/v1/users/me/client-errors` and asserts no single request exceeds server p95 × 3. Regression guard against event-loop starvation.

---

## Dependency graph (compact)

```
                       [main — Phase 0 landed]
                                │
                                ▼
                         CHUNK-F1 (notify_via_threadpool helper)
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
      D-01 (aam-11)    D-02a→D-02b (aam-12a→aam-12b)    D-03 (aam-13)
       recipe_book              recipe               shopping_list
         │                      │                      │
         │                   (parallel x13 total — all D-* chunks)
         │                      │                      │
      D-04 (aam-14)          D-05 (aam-15)          D-06 (aam-16)
     calendar+meal_event      pantry                user_activity
         │                      │                      │
      D-07 (aam-17)          D-08 (aam-18)          D-09 (aam-19)
       search                  import                 user
         │  ▲                   │                      │
         │  │        ┌──────────┘                      │
         │  │        │  (D-08 depends on F2)           │
         │  │        ▼                                 │
         │  │     CHUNK-F2 (boto3 threadpool wrap)    │
         │  │        │                                 │
      D-10 (aam-20)  D-11 (aam-28)  D-12 (aam-29)    D-13 (aam-30)
       admin          friends        parser            recurrence_rule
         │                │            │  ▲              │
         │                │            │  │              │
         └────────┬───────┴────────┬───┴──┘──────────────┘
                  │                │
                  └────────┬───────┘
                           ▼
                  [all domain chunks done]
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
      CHUNK-C1          CHUNK-C2          CHUNK-C3
    startup-guard    error-mw-async      lifespan-pre-warm
         │                 │                 │
         └─────────────────┼─────────────────┘
                           ▼
                      CHUNK-C4 (cutover + shim removal)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           CHUNK-C5      CHUNK-C6     CHUNK-C7
           OpenAI        Firebase     baseline
           async         threadpool   snapshot
                           │
                           ▼
                        CHUNK-C8 (concurrent load test)
                           │
                           ▼
                    [migration complete]
```

### Serial gates (anything else parallelizes)

1. **F1 before any D-\*** (domain chunks need `notify_via_threadpool`).
2. **F2 before D-08** (parser/import boto3 wrap).
3. **All D-\* before C1–C4.**
4. **C1 + C2 + C3 before C4** (C4 is the delete-sync-surface PR — only safe after guards in place).
5. **C4 before C5 / C6 cleanup verifications** (wait for sync surface to be gone).
6. C7, C8 after C5/C6.

### Safe-to-parallelize

- All 13 domain chunks (D-01..D-13) concurrent after F1.
- F2 concurrent with any D-\* except D-08.
- C1, C2, C3 concurrent with each other.
- C5, C6, C7 concurrent with each other.

---

## Sprint-status additions

Append to `_bmad-output/implementation-artifacts/sprint-status.yaml` under the existing `epic-api-async-migration` section:

```yaml
  aam-28-friends-domain-async: backlog
  aam-29-parser-domain-async: backlog
  aam-30-recurrence-rule-domain-async: backlog
  aam-foundations-notify-threadpool-helper: backlog
```

The other story IDs (aam-7..aam-9, aam-11..aam-20, aam-22..aam-27) already exist and stay `backlog` → flipped `review` → `done` by each chunk's /dev loop.

---

## Launch sequence (what to paste into parallel terminals)

**Step 1 — foundations (serial):**

```
/dev aam-foundations-notify-threadpool-helper
```

Then in parallel:

```
/dev aam-9-boto3-threadpool-wrap
```

**Step 2 — 12 parallel domain terminals (spawn all at once after F1 merges):**

```
/dev aam-11-recipe-book-domain-async
/dev aam-12a-recipe-reads-async       # run first
# /dev aam-12b-recipe-writes-async    # run AFTER 12a lands (needs async _response.py)
/dev aam-13-shopping-list-domain-async
/dev aam-14-calendar-and-meal-event-domain-async
/dev aam-15-pantry-domain-async
/dev aam-16-activity-domain-async
/dev aam-17-search-domain-async
/dev aam-19-user-profile-push-tokens-async
/dev aam-20-admin-domain-async
/dev aam-28-friends-domain-async
/dev aam-29-parser-domain-async          # wait for aam-9 to merge first
/dev aam-30-recurrence-rule-domain-async
```

(D-08 import runs after F2 lands:)

```
/dev aam-18-import-job-domain-async
```

**Step 3 — Phase 2 cleanup (after all D-\* merged):**

```
# Parallel:
/dev aam-25-sync-in-async-startup-guard
/dev aam-22-error-tracking-middleware-async
/dev aam-23-lifespan-and-pre-warm

# Sequential:
/dev aam-24-cutover-and-shim-removal

# Parallel again:
/dev aam-7-openai-async
/dev aam-8-firebase-threadpool-wrap
/dev aam-26-latency-baseline-snapshot
/dev aam-27-concurrent-load-integration-test
```

---

## Execution invariants every dev agent must honor

1. **No new abstractions.** Smallest change wins. `Endpoint` → `AsyncEndpoint`, `def` → `async def`, `.query()` → `await db.execute(select(...))`. Nothing else.
2. **No test deletions.** Rewrite the mock shape; preserve every test name and assertion.
3. **No `git add -A`.** Stage file-by-file — parallel agents will collide in `sprint-status.yaml`.
4. **No touching reference domains.** meal / cooking_log / timer / units / invitations / invite_links / client_latency / chat / flags — already converted, don't regress.
5. **No touching WebSocket handlers.** `recipe_book_websocket`, `shopping_list_websocket` stay async.
6. **100% coverage holds.** If a converted line is hard to cover, pair-solve with a test — don't `# pragma: no cover` without a matching note in the PR body.
7. **Lint + test + full CI green before merge.** No bypass.
8. **Commit trailer:** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
