# Async Migration Runbook

**Owns**: `epic-api-async-migration` (`aam-*` stories)
**Audience**: any engineer (or autonomous loop) converting a domain
from sync `Endpoint` + sync `Database` to `AsyncEndpoint` + `AsyncDatabase`.
**Status**: living doc — update if a new gotcha bites you mid-migration.

This runbook is the contract for per-domain conversion stories
(`aam-10` through `aam-21`). Each one cites this file in its ACs. The
goal: the next engineer who picks up a Phase 3 story doesn't have to
rediscover the rules — they read this, and ship.

## TL;DR — Conversion Recipe (the 8-step loop)

For each Endpoint subclass in your domain:

1. **Swap base class**: `class Foo(Endpoint)` → `class Foo(AsyncEndpoint)`.
2. **Async the execute signature**: `def execute(...)` → `async def execute(...)`.
3. **`await` every DB call**: `self.db.find_by(...)` → `await self.db.find_by(...)`,
   `self.db.create(...)` → `await self.db.create(...)`, etc. The
   `AsyncDatabase` surface is a method-for-method mirror of sync
   `Database` (see [`async_database.py`](../libraries/utils/utils/services/async_database.py)).
4. **`self.db.where(...)` is sync, but its terminals are async**:
   `await self.db.where(Model, owner_id=x).first()` (NOT
   `await self.db.where(...)`). The chainable steps build the statement
   without awaiting.
5. **Raw SQLAlchemy stays explicit**: `self.db.db.query(...)` → `await self.db.db.execute(select(...))`.
   `result.scalars().all()`, `result.scalar_one_or_none()`.
6. **Wrap external sync SDKs in `run_in_threadpool`**: Firebase
   `messaging.send`, boto3, anything else that blocks. (`aam-7/8/9`
   pre-wrap the common ones.)
7. **`selectinload` for 1-to-many, `joinedload` for 1-to-1** —
   exact same rule as the sync world. **MissingGreenlet** is the async
   equivalent of `DetachedInstanceError`; it fires when a response
   builder reaches for an unloaded relationship attribute outside the
   session. **Always declare the load up-front in the query.**
8. **Tests convert with the handler**: sync `client` fixture →
   `async_client` fixture; `mock_db` → `mock_async_db`; `count_queries(mock_db)` →
   `count_queries()` (no arg — listens to the engine).

For each router file in your domain:

1. `Depends(get_database)` → `Depends(get_async_database)`.
2. `Depends(get_current_user)` → `Depends(get_current_user_async)`.
3. `return Foo.call(...)` → `return await Foo.call(...)`.
4. **Dual-register**: keep the sync handler file in-tree under an
   ignored path prefix (e.g. `/_legacy_v1/...`) so a one-line revert
   restores prod. Don't delete it until `aam-24`.

For the domain's MCP tool file (`services/api/src/mcp_server/tools/<domain>.py`):

1. `call_endpoint(EndpointCls, ...)` → `await call_endpoint_async(EndpointCls, ...)`.
2. Verify with the MCP smoke test (see [MCP](#mcp-server-conversion) below).

## Decision Matrix — `selectinload` vs `joinedload` vs `noload`

| Relationship type   | Use            | Why                                                                          |
|---------------------|----------------|------------------------------------------------------------------------------|
| 1-to-1              | `joinedload`   | Single JOIN; cheap; no fanout multiplication.                                 |
| 1-to-many (small N) | `selectinload` | Two queries: parent + IN-clause for children. No row fanout.                  |
| 1-to-many (large N) | `selectinload` | Same — `joinedload` would multiply rows then deduplicate (CPU + memory cost). |
| many-to-many        | `selectinload` | Always — `joinedload` fanout is multiplicative across both directions.        |
| Optional/lazy field | `noload`       | Explicit "don't touch this attribute in this code path." Pairs with response- |
|                     |                | shape audits to prove no caller reaches it.                                   |

**One unbreakable rule**: every relationship attribute the response
builder accesses MUST be eager-loaded. See [Lazy-load audit](#lazy-load-audit-procedure).

## Greenlet Bridge — Forbidden Path

`MissingGreenlet` is the runtime symptom of "you opened a sync
`Session` inside an async path." This breaks the event loop and is
exactly what this epic is rooting out.

**Whitelisted sync-on-event-loop paths** (party-mode-locked):

- `services/api/src/middleware/error_tracking.py` — sync error-log
  writer wrapped in `run_in_threadpool`, dedicated 3+2 sub-pool
  (`error_log_engine` from `aam-3`).
- `services/api/src/middleware/latency_capture.py` — `BatchedLatencyWriter`
  daemon thread; owns its own engine.
- `services/api/src/main.py` lifespan — unit-alias pre-warm (one-shot,
  before first request) and `error_log_engine` init.
- `services/api/src/manage.py` — REPL entrypoint; dev-only.

**Anything else** that imports `from utils.services.database import
Database` (sync) into a hot path is a bug. `aam-25` adds a startup
guard that fails the API at boot if a non-whitelisted handler imports
the sync `Database`.

## Lazy-load Audit Procedure

Run this for every converted handler before merging the PR. Goal: prove
no `MissingGreenlet` will fire in prod.

1. **Grep the response-builder path** for ORM attribute chains:

   ```bash
   # Replace <domain> with the file/folder you're converting.
   rg -n '\.(\w+)\.(\w+)' services/api/src/api/v1/<domain>/ \
       --glob '!*test*' \
       --glob '!*__pycache__*'
   ```

2. **For every chain like `model.relation.field`** that appears in the
   response-builder path, confirm `selectinload(Model.relation)` (or
   equivalent) appears in the query that produced `model`.

3. **Cross-check the eager-load list** in your QA walkthrough:

   ```markdown
   ## Lazy-load audit
   Eager loads in this query:
     - selectinload(Meal.recipes)
     - selectinload(Meal.tags)
     - joinedload(Meal.owner)

   Response-builder attribute chains (from grep):
     - meal.recipes[i].name        ← covered by selectinload(Meal.recipes)
     - meal.tags[i].label          ← covered by selectinload(Meal.tags)
     - meal.owner.username         ← covered by joinedload(Meal.owner)
   ```

4. **If a chain isn't covered**, either add the eager load or refactor
   the response builder to not need it. Do NOT ship with an unverified
   chain — `MissingGreenlet` is silent in unit tests (mocks paper over
   it) but fires immediately in prod.

## Dual-Register + Observation Window Procedure

Each domain story lands in a **dual-registered** state for 24-48h.
Async router serves prod traffic; sync handler code stays in-tree as a
fast-revert path.

### Registering both routers

In `services/api/src/main.py` (or the domain's `routers/v1/<domain>_router.py`):

```python
from routers.v1.meal_router import router as meal_router_async
from routers.v1.legacy.meal_router_sync import router as meal_router_sync  # NEW

app.include_router(meal_router_async, prefix="/v1/meals", tags=["meals"])
# Sync sibling under an ignored prefix — never reached by client traffic
# unless we manually flip the registration during rollback.
app.include_router(
    meal_router_sync, prefix="/_legacy_v1/meals", tags=["meals (legacy)"]
)
```

### Rollback during the observation window (< 5 min)

A regression surfaces in `client_latencies` p95 or in error-log volume.
Rollback procedure:

1. In the router-registration block above, swap the prefixes:

   ```python
   app.include_router(meal_router_sync, prefix="/v1/meals", tags=["meals"])
   app.include_router(
       meal_router_async, prefix="/_legacy_v1/meals", tags=["meals (async)"]
   )
   ```

2. `bin/prod-deploy` — ECS rolling deploy completes in ~3 min.

3. Verify in `bin/prod-script services/api/scripts/audit_errors.py
   --window 1h` that the spike subsides; in `analyze_latency.py
   --window 1h` that the affected `normalized_path` p95 returns to
   baseline.

4. File a post-incident note in the story's QA walkthrough capturing
   the symptom + revert commit hash.

### Closing the observation window

After 24-48h with green latency + no error spike on the converted
domain:

1. Mark the story `done` in `sprint-status.yaml`.
2. The sync handler code becomes eligible for `aam-24` deletion (the
   cutover story collects every domain's sync code into one revert and
   removes it).

## Rollback Procedure (post-window, post-aam-24)

Once the sync handler is deleted, rollback is `git revert` of the
specific story commit + `bin/prod-deploy`. Lead time ~10 min.

For `aam-24` itself, rollback is non-trivial because all sync handler
code is gone. The runbook entry: revert to commit-immediately-before-aam-24.
That commit hash is captured in `aam-24`'s QA walkthrough.

## Session-per-Request Lifecycle

```
                   ┌──────────────────────────────────────────────┐
                   │                                              │
HTTP request ──►   │  FastAPI                                      │
                   │     │                                         │
                   │     ├─►  get_async_database (yields           │
                   │     │      AsyncDatabase wrapping             │
                   │     │      AsyncSession from AsyncSessionLocal)│
                   │     │                                         │
                   │     ├─►  get_current_user_async (uses the     │
                   │     │      yielded AsyncDatabase via          │
                   │     │      `await find_or_create_by(...)`)    │
                   │     │                                         │
                   │     ├─►  Handler calls `await Foo.call(...)`  │
                   │     │      → AsyncEndpoint.run()              │
                   │     │      → execute(...)                     │
                   │     │      → returns success(...)             │
                   │     │                                         │
                   │     └─►  AsyncDatabase.close() on yield exit  │
                   │           (returns connection to async pool)  │
                   │                                              │
HTTP response ◄────                                                 │
                   └──────────────────────────────────────────────┘
```

Key invariants:

- **One AsyncSession per request** — yielded by `get_async_database`,
  closed when the dep generator exits.
- **No session sharing across `asyncio.gather` legs** — AsyncSession is
  not concurrency-safe. If a handler fans out to multiple DB calls,
  serialize them on the same session OR open a second session
  explicitly.
- **`asyncio.gather` IS allowed for independent external calls**
  (OpenAI + S3 + DB) when the handler does all three. Saves wall-clock.

## Per-Domain Story Checklist

Use this checklist as the structure of each domain story's QA walkthrough:

- [ ] **Service layer converted** — `<domain>_service.py` async signatures.
- [ ] **All Endpoint subclasses converted** to `AsyncEndpoint`.
- [ ] **Router file** — `Depends(get_async_database)` +
      `Depends(get_current_user_async)` + `await Foo.call(...)`.
- [ ] **Router dual-registered** with sync handler under
      `/_legacy_v1/<domain>` prefix.
- [ ] **MCP tool file converted** — `await call_endpoint_async(...)`.
- [ ] **Test file converted** — `async_client` + `mock_async_db`;
      `count_queries(mock_db)` → `count_queries()`.
- [ ] **Domain event subscribers** (if any) async + registered on async
      dispatcher.
- [ ] **Lazy-load audit** completed — eager-load list + response-builder
      grep output pasted in QA walkthrough.
- [ ] **Baseline captured** — `analyze_latency.py --window 24h` for
      every owned `normalized_path`, day before PR opens.
- [ ] **Async-router merged + dual-registered.**
- [ ] **24-48h observation window** with no >20% p95 regression on any
      owned path.
- [ ] **MCP smoke test** run via
      `services/api/src/mcp_server/client.py` against staging; output
      pasted in walkthrough.
- [ ] **Post-merge capture** — same `analyze_latency.py` numbers; for
      low-traffic endpoints, supplement with synthetic load via
      `tools/load_test_client_latencies.py`.
- [ ] **Story closed** — sprint-status.yaml flipped to `done`; sync
      handler code now eligible for `aam-24` deletion.

## MCP Server Conversion

MCP tools call backend endpoints via a helper. Both helpers coexist
during the migration:

- `call_endpoint(EndpointCls, *args, **kwargs)` — sync, used by
  not-yet-converted MCP tools.
- `call_endpoint_async(EndpointCls, *args, **kwargs)` — async, added by
  `aam-3`, used by converted MCP tools.

Converting an MCP tool file:

```python
# Before
from utils.api.endpoint import Endpoint
from mcp_server.server import call_endpoint

@mcp.tool
def list_meals(...) -> str:
    return call_endpoint(ListMealsEndpoint, ...)

# After
from utils.api.endpoint import AsyncEndpoint
from mcp_server.server import call_endpoint_async

@mcp.tool
async def list_meals(...) -> str:
    return await call_endpoint_async(ListMealsEndpoint, ...)
```

The MCP auth dep (`services/api/src/mcp_server/auth.py::get_current_database`)
also dual-surfaces in `aam-6` — async version `get_current_database_async`
arrives there. After all domains convert, sync MCP variants get pruned
in `aam-24`.

### MCP smoke test

After converting a domain's MCP tool file, run a one-shot smoke test
against staging:

```bash
# Adjust path to wherever the MCP CLI client lands.
poetry run python services/api/src/mcp_server/client.py \
    --tool meal.list_meals --args '{"scope": "home"}' \
    --base-url https://staging.api.palateful.com
```

Paste the output (truncated to ~200 lines) into the story's QA
walkthrough. The point isn't full coverage — it's catching gross
regressions that would otherwise show up as "AI gave a weird answer"
rather than a 500.

## Testing Patterns

### Async client fixture (aam-4)

```python
async def test_get_meal(async_client, mock_async_db, mock_user):
    mock_async_db.set_find_by(
        Meal, MockMeal(id=meal_id, owner_id=mock_user.id),
        id=meal_id,
    )

    response = await async_client.get(f"/v1/meals/{meal_id}")
    assert response.status_code == 200
```

### Counting queries on a real engine

For tests against a real test DB (less common — most API tests stay on
mocks), `count_queries()` with no args attaches `before_cursor_execute`
listeners to `db_engine` and `async_db_engine.sync_engine`:

```python
async def test_no_n_plus_one(async_db_session):
    # Setup: create test data using async_db_session...
    with count_queries() as qc:
        result = await some_async_function(async_db_session)

    assert qc.select <= 3  # Catches N+1 regressions
```

### Sync mock-db tests (legacy, unchanged)

`count_queries(mock_db)` continues to work for every existing pbq-*
test. The two pathways feed the same `QueryCounter`.

## Common Mistakes & Their Fixes

| Mistake                                              | Symptom                                  | Fix                                                                          |
|------------------------------------------------------|------------------------------------------|------------------------------------------------------------------------------|
| Forgot `await` on a DB call                          | Coroutine returned, AttributeError later | `await self.db.find_by(...)`                                                  |
| Lazy-loaded a relationship after session close       | `MissingGreenlet` at attribute access    | Add `selectinload(Model.relation)` to the query                              |
| Used sync `session.begin_nested()` in async handler  | `sa.exc.InvalidRequestError`             | `async with session.begin_nested():`                                          |
| Called sync `Database()` from async handler          | Pool exhaustion under load               | Use `get_async_database` dep; sync stays only in whitelisted paths           |
| Wrapped `messaging.send` in `await` directly         | `TypeError: object NoneType ...`         | `await run_in_threadpool(messaging.send, ...)`                                |
| `asyncio.gather` two queries on the same session     | `IllegalStateChangeError`                | Serialize, or open a second session                                          |
| Replaced `pbq-*` test's `count_queries(mock_db)` arg | Test stops measuring                     | Keep the mock_db arg — pathway is additive                                    |
| Removed sync handler code before observation window  | Multi-file revert needed if regression   | Wait until `aam-24`. Dual-registered prefix is enough until then.            |

## Decision Log

(Captured from party-mode 2026-04-23. Update when this runbook needs amendment.)

- **2026-04-23** (party-mode): observation window default 48h fixed +
  synthetic-load supplement. MCP smoke test mandatory per domain.
  Dual-register + ignored-prefix pattern selected over
  registration-toggle to keep rollback git-grep-free.
- **2026-04-23** (party-mode): `count_queries` rewrite is additive —
  must NOT change `pbq-*` test ergonomics. Both pathways feed the same
  `QueryCounter`; existing assertions keep running.
- **2026-04-23** (party-mode): `MissingGreenlet` audit is mandatory per
  Phase 3 story. The grep-based procedure above is the sanctioned
  technique; a code reviewer who can't see the grep output in the QA
  walkthrough should block the merge.
