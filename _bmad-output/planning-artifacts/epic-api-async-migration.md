<!-- refined via party-mode 2026-04-23 -->

# Epic: API Async SQLAlchemy Migration

## Overview

`services/api` declares every router handler `async def` but calls a **synchronous** `Endpoint.call(...)` inline. `.call()` runs sync SQLAlchemy queries on the event loop, so any long-running handler (imports, OpenAI, batched inserts) blocks **every other in-flight request** for its entire duration. On 2026-04-23 the debug tooling surfaced the consequence clearly: `GET /v1/meals/{meal_id}` had server-side p95 = **188ms** but client-observed wall-clock p95 = **5192ms**. The gap is queue-wait while the event loop is held by other handlers. `POST /v1/users/me/client-errors` shows the tell: p50 = 50ms, p95 = 5931ms — a fast write starved behind slow neighbors.

Two fixes were considered:

- **Option 1:** swap handler declarations to `def` so Starlette auto-dispatches to its threadpool. Cheap, ~1 day, reversible per-router; solves event-loop starvation at the single-user scale we run at today.
- **Option 2 (this epic):** migrate the whole API to async SQLAlchemy + async handlers + async-native SDKs. Bigger job; preserves single-worker async, unlocks parallel DB fan-out (`asyncio.gather`), and gets the architecture aligned with what FastAPI is designed for.

Per the user's 2026-04-23 decision, we're taking option 2. Party-mode (2026-04-23) sharpened this draft: pool math fixed, MCP surface brought in-scope, test-helper back-compat for worker tests locked, dual-dispatch cutover replacing big-bang flip, and acceptance evidence gates tightened against "silent drift" failure modes.

## Goal

1. `GET /v1/meals/{meal_id}` client-observed p95 returns to < 500ms (today: 5192ms spike, 188ms server).
2. `POST /v1/users/me/client-errors` server-side p95 returns to < 200ms (today: 5931ms).
3. No handler in `services/api` holds the event loop for its DB work. A slow handler no longer starves fast neighbors.
4. `services/api` runs on `asyncpg` + `AsyncSession` + `AsyncClient` end-to-end. `psycopg2` + sync `Session` remain in the process only for: error-log writes, batched latency writers, unit-alias pre-warm, `manage.py` REPL. All explicitly whitelisted off the event loop.
5. 100% API coverage gate stays green throughout. Per-story PRs maintain coverage; no temporary exemptions. The dual-path test burden is bounded by the contract that each domain story converts sync tests to async tests in the same PR — no parallel sync+async test suites on the same handler.
6. Ops scripts + `bin/prod-script` + `bin/prod-console` + `services/worker` continue to work unchanged (sync engine). The worker's reliance on `libraries/utils` must not break mid-migration — contract pinned in `aam-2` and `aam-4`.

## End-User Flow

End user sees exactly what they see today, but faster and with no random multi-second stalls:

1. Leo opens the app. Home meal grid loads. Client-observed latency for `GET /v1/meals` stays in line with its server-side p95 (~150ms), not 10× it.
2. He taps a meal. `GET /v1/meals/{id}` returns < 500ms client-observed even if he hit "Import this TikTok" five seconds earlier — the background import no longer holds the event loop.
3. He navigates to Activity while the import worker is still parsing. The screen renders immediately; no spinner past 1s.
4. From the admin surface: `bin/prod-script services/api/scripts/analyze_latency.py --window 24h --section all` post-cutover shows `/v1/meals/:id` p95 (client) under 500ms and no endpoint showing starvation-pattern tails (p50 fast, p95 several seconds).
5. **The win is measurable within 24h of `aam-24` landing** via the `cla-*` client-latency pipeline. No invisible improvement — every story's QA walkthrough cites a concrete p50/p95 delta.

## Frontend Changes

**None.** Response shapes are byte-identical; the client never knew or cared how the server reached them. Flutter code doesn't change. This is a backend-only epic. The "user sees faster" outcome measures via the existing `cla-*` client-latency pipeline and `ptd-*` debug overlay — no new instrumentation.

**UX-silent-regression guards** (party-mode addition):

- WebSocket handlers (`recipe_book_router`, `shopping_list_router`) covered in their domain stories with an explicit reconnect-burst test to catch any auth-dep race introduced by switching `get_current_user` → `get_current_user_async` on WS upgrade.
- Pull-to-refresh timing tracked via the existing `route_paint` client-latency event — no new metric, but every Phase 3 story's QA walkthrough names the routes it owns and pastes their pre/post `route_paint` p95.
- Push-notification UX unchanged: `aam-8` wraps Firebase synchronously via `run_in_threadpool`; the wall-clock for `messaging.send` from inside a handler is unchanged ±~1ms (threadpool-hop cost).

## Backend Changes

See the **Stories** section below for per-story detail. Cross-cutting primitives that every story inherits:

- **Dual engine, same database.** One sync `create_engine(...)` (psycopg2) + one async `create_async_engine(...)` (asyncpg) in the API process. Both connect to the same Postgres. **Pool budget re-derived in party-mode (see Design Principles).** Sync pool shrinks to 5/10 once only the whitelisted paths use it; async pool takes the 20/40 budget. Total API-process peak = 75 connections — still over `max_connections=60`, so **`aam-1` ships a terraform PR raising `max_connections` to 100** (parameter-group change, no restart required for superuser connections but requires a reboot for regular clients; the reboot is part of `aam-1`'s deploy plan).
- **Dual Database surface.** `libraries/utils/utils/services/database.py` (sync `Database`) stays. New `libraries/utils/utils/services/async_database.py` (`AsyncDatabase`) added with mirror surface: `find_by`, `find_or_create_by` (incl. async `pg_advisory_lock`), `create`, `create_all`, `update`, `save`, `delete`, `bulk_update`, `where`. **Worker contract pinned**: the sync `Database` public API is frozen for the duration of the migration (no signature changes, no rename, no deprecation decorator) so `services/worker` + `services/parser` + ops scripts keep building. `aam-2`'s CI job re-runs the worker's test suite against the modified `libraries/utils` as a gate.
- **Dual Endpoint surface.** `Endpoint` (sync) stays. New `AsyncEndpoint` added with `async def execute`, `async def run`, `async def call`. `_log_error_to_db` runs in the sync `Database()` via `run_in_threadpool` — error logs are rare, separate session, fire-and-forget. **Deadlock risk addressed**: the sync error-log session uses a dedicated 3-connection sub-pool that is never borrowed from async hot path, so the threadpool hop cannot re-enter a pool already held by the async engine.
- **Dual FastAPI dependency surface.** New `get_async_database` dep yields `AsyncDatabase`. New `get_current_user_async` dep uses `AsyncDatabase` for the `find_or_create_by` / `_finalize_auth` / `_ensure_default_calendar` dance (async `session.begin_nested()` + `IntegrityError` catch).
- **External SDK swaps.** OpenAI → `AsyncOpenAI` at every callsite in `services/api/src/`. Firebase Admin `messaging.send*` → `run_in_threadpool` (SDK is sync-only upstream). boto3 presign + S3 → `run_in_threadpool` (22 callsites).
- **MCP server in scope.** `services/api/src/mcp_server/tools/*.py` call foundation endpoints via `call_endpoint(endpoint_cls, *args, **kwargs)`. `call_endpoint` gets an async sibling `call_endpoint_async` in `aam-3`; MCP tools convert alongside their domain story (e.g. `meals.py` MCP tools in `aam-10`, `recipes.py` in `aam-12`, etc.). MCP auth dep `mcp_server/auth.py::get_current_database` also dual-surfaced in `aam-6`.
- **Per-router dual-dispatch cutover (party-mode change).** Each domain story ships its router in a **dual-registered** state for a 24-48h observation window: the async router is registered, the sync router stays under an ignored path prefix. This is **not** traffic-splitting — prod traffic hits the async router immediately. The sync handler code survives in the repo for that window so a revert is a single-line router-registration swap, not a multi-file re-revert. `aam-24` deletes the sync handler code after every domain's observation window closes green.
- **Greenlet bridge forbidden.** Any remaining sync `Session` call inside an async handler is a bug. Post-cutover, a startup guard in `main.py` enumerates open sessions by engine and fails fast if sync sessions are opened anywhere outside the whitelisted paths (error-log, batched writers, unit-alias pre-warm, `manage.py` REPL).
- **Lazy-load audit (new AC, every Phase 3 story).** Every converted handler's QA walkthrough lists every `selectinload` / `joinedload` / `noload` used in its query tree AND explicitly greps for `.` chains on ORM attributes in the response-builder path, confirming each one is covered by an eager load. `MissingGreenlet` in async is the equivalent of sync `DetachedInstanceError` but fires differently (at attribute-access, not at first query) — the grep is the regression guard.
- **`count_queries` helper back-compat locked (party-mode).** The `before_cursor_execute` rewrite in `aam-4` must preserve the exact `QueryCounter` public surface (`.total`, `.select`, `.insert`, `.update`, `.delete`) so every `pbq-*` query-count assertion keeps running without edit. Rewrite is additive — async engine event listener registers alongside sync engine's — and `aam-4` pins this with a regression test that runs **both** a sync and async test against the same counter.
- **Domain event bus.** Dispatcher (`libraries/utils/utils/services/domain_events/dispatcher.py`) gains an `async def dispatch(...)` method alongside the sync `dispatch(...)`. Subscribers registered as sync stay sync (worker uses them); subscribers registered as async are awaited from the async dispatcher path. Dispatcher keeps a per-subscriber async/sync flag. Story `aam-13` (shopping-list subscriber) and `aam-15` (pantry subscriber) convert their subscribers to async and register them on the async dispatcher; the sync dispatcher is still called by the worker for worker-path events.

## Infrastructure Changes

- **One terraform change**: `aws_db_parameter_group` `max_connections` = 60 → 100 (ships in `aam-1`; requires one RDS reboot during a quiet window; rollback = revert the PG change + reboot). This makes the dual-engine pool arithmetic correct and leaves 25 connections of headroom for beat/worker/migrator.
- **One new pip dep**: `asyncpg`. `psycopg2-binary` stays.
- **Two new env vars** (optional, default matches today's sync budget): `DB_ASYNC_POOL_SIZE=20`, `DB_ASYNC_MAX_OVERFLOW=40`. Read in code at async-engine creation; task definition gets explicit values in `aam-1`'s PR so rollback behavior is deterministic. **`DB_POOL_SIZE` / `DB_MAX_OVERFLOW` reduced** to `5` / `10` in `aam-24` once only whitelisted paths use the sync engine — separate PR inside the cutover story.
- **Healthcheck unchanged.** `/v1/health` is stateless; migrates implicitly to the async engine but doesn't hit DB.
- **Cold-start mitigation (party-mode).** `asyncpg`'s first-query prepared-statement cache build adds ~100-300ms to the very first async query per connection. `aam-23` adds a lifespan pre-warm that runs a trivial `SELECT 1` on every pool connection at startup before the health check flips green, masking the blip from any real request. ECS task's `startPeriod` stays at 60s (already generous).
- **ECS rolling deploy.** Existing circuit-breaker + rolling-update config handles connection drain. No per-task hand-holding needed.
- **Rollout is big-bang per-router + observation window + full revert.** Each domain story is its own PR that lands incrementally in prod, dual-registered for 24-48h. The "cutover" story (`aam-24`) is the moment the last sync handler code is deleted and sync dependency shims get pruned. Rollback for any individual story during its observation window = one-line router-registration swap + `bin/prod-deploy` (< 5 min). Rollback after the observation window closed = `git revert + bin/prod-deploy` (~10 min). No canary traffic-splitting; the observation window is the safety net.

## Design Principles

**Party-mode 2026-04-23 locked decisions:**

1. **No sync DB calls on the event loop.** Ever. Exceptions (whitelisted): the error-log writer (via threadpool), `BatchedLatencyWriter`/`BatchedTaskWriter`/`BatchedClientLatencyWriter` (daemon threads, own engine), unit-alias pre-warm (one-shot at lifespan startup, before first request), `services/api/src/manage.py` REPL (dev-only entrypoint).
2. **`asyncio.gather` is allowed only where it's free.** Don't parallelize queries that share a session (SQLAlchemy async sessions are not concurrency-safe). Parallelize independent external calls (OpenAI + S3 + DB) when a handler does all three.
3. **`selectinload` for 1-to-many, `joinedload` for 1-to-1.** Same rule as `epic-perf-backend-query-tuning`. Async changes nothing about how you express the query; it just removes the blocking.
4. **No lazy loading after session close.** All relationship loads declared in the query (`selectinload(...)`). `MissingGreenlet` replaces `DetachedInstanceError` and fires differently — every Phase 3 story's QA walkthrough greps the response-builder path for ORM attribute chains and confirms each is eager-loaded.
5. **`async with session.begin_nested()` replaces `session.begin_nested()`.** One-line port. `_ensure_default_calendar`'s IntegrityError-catch pattern carries over verbatim; locked in `aam-6` with a concurrent-request race test.
6. **Pool arithmetic, re-derived (party-mode correction to draft):** sync API 5/10 post-cutover + async API 20/40 + beat/worker/migrator 15 + headroom 10 = 100. `aam-1` raises `max_connections` to 100. Sync pool stays 10/20 **until** `aam-24` shrinks it (separate PR inside the cutover story).
7. **Per-router rollback must be fast.** Dual-registered state for the 24-48h observation window; rollback = one-line router-registration swap, not a multi-file revert. After the window closes green, sync handler code is deleted in `aam-24`.
8. **Smallest change wins.** Don't refactor domain logic while converting. Don't reshape query patterns. Don't introduce new abstractions. The scope is "sync → async", not "also clean up X".
9. **Measure each domain story with `analyze_latency.py` + `client_latencies`.** Baseline captured 24h BEFORE the PR opens (from `ptd-*` snapshot). Post-merge capture 24h after landing. **If traffic is too low for a 24h post-merge window to be statistically meaningful on a given endpoint, the story names a synthetic-load test that reproduces the shape** (reuse `tools/load_test_client_latencies.py` pattern). Pasted into QA walkthrough. p95 regresses >20% on any owned `normalized_path` → halt + investigate before closing story.
10. **Tests convert as handlers convert.** Sync `TestClient` for sync handlers, `AsyncClient` + `ASGITransport` for async handlers, both hitting the same app. Per-story converts its own domain's test file. **No parallel sync+async test files for the same handler.** Coverage bar stays 100% per PR — the dual-path burden is bounded by "both paths exist only for the dual-registered window, and tests cover the active path."
11. **Coverage at 100%, always.** Per-story PR includes new async-path tests. No merging into `main` with coverage < 100%.
12. **MCP server migrates in lockstep.** Each domain story's scope explicitly includes that domain's MCP tool file + the `call_endpoint_async` swap. MCP agent/chat traffic is low-volume — no separate observation window needed, but regression risk is real because MCP-tool failures surface as "AI gave me a weird answer" not a 500.
13. **Worker contract frozen.** `libraries/utils/utils/services/database.py` public API does not change shape for the duration of the migration. CI gate in `aam-2` re-runs worker's test suite against the library PR as a blocking check. No deprecation decorators on sync methods until post-cutover cleanup epic.
14. **Dispatcher dual-path.** Domain-event dispatcher gains an async dispatch path alongside sync. Per-subscriber async/sync flag. Worker uses sync dispatch; API uses async dispatch post-conversion.
15. **Observation window before delete.** Sync handler code survives in the repo for 24-48h per domain as the fast-revert path. `aam-24` deletes after all windows have closed green.

## File Structure

```
libraries/utils/utils/services/database.py                    (unchanged — sync API FROZEN for duration of migration; stays for scripts + writers + worker + manage.py)
libraries/utils/utils/services/async_database.py              (new — AsyncDatabase class)
libraries/utils/utils/services/domain_events/dispatcher.py    (modify — add async dispatch path + per-subscriber async flag)
libraries/utils/utils/api/endpoint.py                         (modify — add AsyncEndpoint class; Endpoint stays)
libraries/utils/utils/constants.py                            (modify — DB_ASYNC_POOL_SIZE / DB_ASYNC_MAX_OVERFLOW)
libraries/utils/utils/services/meal_service.py                (modify — async rewrite in-place; see aam-10)
libraries/utils/utils/services/pantry_service.py              (modify — aam-15)
libraries/utils/utils/services/activity_service.py            (modify — aam-16)
libraries/utils/utils/services/domain_events/                 (modify — subscribers go async; aam-13, aam-15)
libraries/utils/utils/services/push_notification.py           (modify — run_in_threadpool wraps; aam-8)

terraform/modules/rds/parameter_group.tf                      (modify — max_connections 60 → 100; aam-1)

services/api/pyproject.toml                                   (modify — add asyncpg)
services/api/src/main.py                                      (modify — async engine init on lifespan + pre-warm; aam-1 + aam-23)
services/api/src/dependencies.py                              (modify — add get_async_database + get_current_user_async; aam-6)
services/api/src/middleware/error_tracking.py                 (modify — run_in_threadpool the sync logger; aam-22)
services/api/src/mcp_server/server.py                         (modify — add call_endpoint_async; aam-3)
services/api/src/mcp_server/auth.py                           (modify — async get_current_database; aam-6)
services/api/src/manage.py                                    (unchanged — REPL uses sync surface; whitelisted)

services/api/src/routers/v1/*.py                              (modify — dual-register during window, then flip; aam-10..aam-21)
services/api/src/api/v1/**/*.py                               (modify — every Endpoint subclass converts; aam-10..aam-21)
services/api/src/mcp_server/tools/*.py                        (modify — MCP tools go async alongside their domains; aam-10..aam-20)

libraries/test_helper/conftest.py                             (modify — add async_db_session, async_client; aam-4)
libraries/test_helper/async_db.py                             (new — async test engine + session factory; aam-4)
libraries/test_helper/...                                     (SYNC FIXTURES FROZEN — worker depends on them; aam-4 adds alongside, doesn't replace)
services/api/tests/conftest.py                                (modify — async fixtures + rewritten count_queries; aam-4)
services/api/tests/**/*.py                                    (modify — per-domain test conversion)
services/worker/tests/...                                     (UNCHANGED — aam-2 / aam-4 CI gates re-run this suite against library PRs)

docs/async-migration-runbook.md                               (new — aam-5; per-handler conversion recipe + rollback + observation-window procedure)

_bmad-output/implementation-artifacts/aam-*-qa-walkthrough.md (generated per story)
```

**What does NOT change:**

- `services/worker/`, `services/parser/`, `services/migrator/` — stay fully sync.
- `bin/prod-script`, `bin/prod-console`, `services/api/scripts/*.py`, `services/api/src/manage.py` — keep using sync `Database` + sync engine.
- `BatchedLatencyWriter`, `BatchedTaskWriter`, `BatchedClientLatencyWriter` — daemon threads keep their own sync engine.
- Flutter client — no changes.
- Response shapes — byte-identical.

## Stories

### Phase 1 — Foundations (6 stories, mostly serial)

**`aam-1-async-engine-and-rds-capacity`** — wire async engine + AsyncSession factory + `get_async_database` dep + raise RDS `max_connections`.

ACs:
- `services/api/pyproject.toml` adds `asyncpg`.
- `libraries/utils/utils/constants.py` adds `DB_ASYNC_POOL_SIZE` (default 20) + `DB_ASYNC_MAX_OVERFLOW` (default 40) with env override.
- `services/api/src/main.py` lifespan creates `async_engine = create_async_engine(async_url, pool_size=..., max_overflow=...)` + `AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)`. Disposes on shutdown.
- Startup ordering: **sync engine first** (writers depend on it at lifespan-startup for the pre-warm), **async engine second**. Dispose order reversed.
- `services/api/src/dependencies.py` adds `async def get_async_database() -> AsyncGenerator[AsyncDatabase, None]` yielding a request-scoped `AsyncDatabase` (placeholder — real class arrives in `aam-2`; this story uses a stub that wraps `AsyncSession`).
- ECS task definition env vars: `DB_ASYNC_POOL_SIZE=20`, `DB_ASYNC_MAX_OVERFLOW=40` explicitly set in terraform for rollback determinism.
- **Terraform**: `aws_db_parameter_group` `max_connections` 60 → 100. Deploy plan includes the RDS reboot window (pick a quiet hour; notify beat/worker they'll reconnect). Post-reboot check: `SELECT current_setting('max_connections')` returns `100`.
- **Rollback plan documented inline in the PR**: `terraform apply` reverting parameter-group value + RDS reboot; ECS task definition reverts via the same commit.
- Test: one dummy async handler (not routed) exercises the dep at test-time; real usage lands later.
- Lands **dark** — no production handler uses the async engine yet.

**`aam-2-async-database-class-and-worker-contract-gate`** — `AsyncDatabase` mirror + worker regression gate.

ACs:
- New file `libraries/utils/utils/services/async_database.py`.
- Public methods: `find_by`, `find_or_create_by`, `create`, `create_all`, `update`, `update_all`, `save`, `save_all`, `delete`, `bulk_update`, `find_and_bulk_update`, `where`, `lock`, `close`.
- `find_or_create_by` implements the advisory-lock + check-insert-check pattern via `await session.execute(text("SELECT pg_advisory_lock(:k)"), {"k": key_hash})` inside an async context manager. Behavior parity with sync version verified by a side-by-side test: two parallel invocations with the same key create exactly one row.
- `lock()` returns an async context manager that acquires/releases `pg_advisory_lock`.
- Sync `Database` public API **unchanged** — verified by a signature-diff test (introspects `Database` class at import time, pickles a canonical signature set, asserts equality against a checked-in baseline).
- **CI gate**: `npx nx run worker:test` + `npx nx run parser:test` run against the library diff. Both green required to merge. (Integrates with the existing NX project graph — no new CI config.)
- All unit tests for sync `Database` get async twins in `test_async_database.py`. 100% coverage.
- Lands **dark**.

**`aam-3-async-endpoint-base-and-mcp-helper`** — `AsyncEndpoint` class + error-log bridge + `call_endpoint_async`.

ACs:
- `libraries/utils/utils/api/endpoint.py` adds `AsyncEndpoint` class alongside `Endpoint`.
- `AsyncEndpoint.call(cls, *args, **kwargs)` → `await AsyncEndpoint(*args, **kwargs).run()` → `await self.execute(...)` → `handle_result(...)`.
- `_log_error_to_db` kept sync; invoked from async path via `await run_in_threadpool(self._log_error_to_db, error)`. **Dedicated sub-pool**: sync error-log `Database()` uses a separate small engine (pool_size=3, max_overflow=2) so the threadpool hop cannot contend with any other sync pool. Verified by a stress test that fires 50 concurrent handler errors and asserts no pool-exhaustion.
- `services/api/src/mcp_server/server.py` adds `async def call_endpoint_async(endpoint_cls: type[AsyncEndpoint], *args, **kwargs) -> str` alongside the existing sync `call_endpoint`. Both coexist until cutover.
- Zero subclasses yet — base class only (+ the MCP helper function).
- Test: fake `AsyncEndpoint` subclass exercises all code paths (success, APIException, unhandled Exception → DB log).
- Lands **dark**.

**`aam-4-async-test-fixtures-and-counter-parity`** — async test fixtures + engine-agnostic `count_queries` + back-compat with `pbq-*` tests and worker tests.

ACs:
- `libraries/test_helper/async_db.py` provides `async_engine` + `async_db_session` (nested-tx rollback on AsyncSession, parity with sync fixture).
- `libraries/test_helper/conftest.py` + `services/api/tests/conftest.py` add `async_client` fixture using `httpx.AsyncClient(transport=ASGITransport(app=app))`.
- Existing sync `db_session` / `client` fixtures unchanged — worker + parser test suites continue to import them. Additive, not replacement.
- `count_queries` context manager rewritten to use SQLAlchemy `before_cursor_execute` event on both sync and async engines. Exact public API preserved: `qc.total`, `qc.select`, `qc.insert`, `qc.update`, `qc.delete`.
- **Back-compat regression test**: one test file imports the rewritten `count_queries`, runs it across (a) a sync endpoint call, (b) an async endpoint call, (c) an N+1 scenario that must count ≥N queries. All three pass. This is the canary for every `pbq-*` assertion.
- **CI gate**: `npx nx run worker:test` re-runs against the `libraries/test_helper` diff to confirm sync fixtures work unchanged.
- One demo test in `test_async_endpoint.py` exercising the async fixture end-to-end through an unrouted test-only endpoint.
- `pyproject.toml`: pytest-asyncio mode stays `auto` (no change — works for both sync and async tests).

**`aam-5-migration-runbook`** — conversion recipe + rollback doc + observation-window procedure.

ACs:
- New `docs/async-migration-runbook.md`:
  - Per-handler conversion recipe (base class swap, query rewrite, `selectinload` rule, `await`-every-DB-call rule, `run_in_threadpool` for sync SDKs).
  - `selectinload` / `joinedload` / `noload` decision matrix.
  - Greenlet-bridge-forbidden rule + rationale (+ whitelist of OK-to-stay-sync paths).
  - **Lazy-load audit procedure**: grep pattern + eyeball-audit checklist for the response-builder path (specific shell one-liner to grep for dot-chains on ORM attrs that aren't in a `selectinload`).
  - **Dual-register + observation-window procedure**: how to register async router, keep sync handler file, how to flip prod traffic, how to flip back in < 5 min.
  - Rollback procedure (both during observation window AND after): specific commands.
  - Session-per-request lifecycle diagram.
  - Checklist for per-domain story: convert service → convert handlers → convert MCP tools → flip router dep → convert tests → capture baseline → register async router → merge + observe 24-48h → measure latency → close sync handler → green CI → close story.
  - **MCP-specific call-out**: MCP tools call `call_endpoint_async(...)` post-conversion; `services/api/src/mcp_server/auth.py::get_current_database` has both sync and async variants.
- Referenced from every subsequent story's ACs.

**`aam-6-async-auth-deps`** — async `get_current_user` + async MCP `get_current_database` + concurrent-request race test.

ACs:
- `services/api/src/dependencies.py` adds `async def get_current_user_async(authorization: Annotated[str, Header()], database: AsyncDatabase = Depends(get_async_database)) -> User`.
- Calls `await database.find_or_create_by(User, auth0_id=..., defaults=...)`.
- `_finalize_auth_async(database, user, claims)` implemented.
- `_ensure_default_calendar_async(database, user)` uses `async with session.begin_nested()` + `IntegrityError` catch — preserves race-safety contract (`epic-perf-infra-and-measurement` lock #5).
- `services/api/src/mcp_server/auth.py` gains `get_current_database_async` alongside the existing sync version. Both return the correct typed Database/AsyncDatabase.
- Sync `get_current_user` remains; no router switches deps yet.
- **Race test**: 5 parallel `asyncio.gather` calls to the async auth flow for a brand-new Auth0 user; assert exactly one user row + one default calendar created. Covers the known concurrency trap.
- **WebSocket auth probe**: a unit-level test confirms `get_current_user_async` works inside a WS upgrade dep chain (WS dep resolution differs subtly from HTTP in FastAPI; catches the issue early).
- Lands **dark** — no router uses the async dep.

### Phase 2 — External SDK async swaps (3 stories, parallel after aam-1)

**`aam-7-openai-async`** — swap `OpenAI` → `AsyncOpenAI` at all API callsites.

ACs:
- `services/api/src/api/v1/search/generate_recipe_embedding.py` + peers (3 callsites total) use `AsyncOpenAI`. Every call is `await`ed.
- The callsites' wrapping `Endpoint` subclasses may stay sync in this story; await is inside a `run_in_threadpool` wrapper until their domain story (aam-17) converts them. The runbook (`aam-5`) documents this bridge pattern.
- Net behavior unchanged; no shape change.
- Coverage stays at 100%.

**`aam-8-firebase-threadpool-wrap`** — `messaging.send*` via `run_in_threadpool`.

ACs:
- `libraries/utils/utils/services/push_notification.py` wraps every `messaging.send(...)` / `messaging.send_each_for_multicast(...)` call in `await run_in_threadpool(messaging.send, ...)`. 28 callsites.
- Callers that were sync stay sync (worker-side push paths still use the sync variant); callers that are async use the async variant. Helper exposes **both** `send_push(...)` (sync) and `send_push_async(...)` (async) — neither deprecated.
- Test: existing push_notification tests stay green; new test verifies async-path invokes threadpool (mocked).
- Lands **dark** (no hot-path async caller yet).

**`aam-9-boto3-threadpool-wrap`** — presign + S3 via `run_in_threadpool`.

ACs:
- 22 boto3 callsites under `services/api/src/api/v1/import_job/`, `services/api/src/api/v1/parser/`, `services/api/src/api/v1/recipe/`, and `get_logs.py` wrapped in `run_in_threadpool` (when called from async paths).
- CloudWatch Logs read in `get_logs.py` wrapped behind `run_in_threadpool` on the async path.
- Test: existing import/parser tests stay green.

### Phase 3 — Per-domain conversions (12 stories, parallelizable after aam-2/3/4/6)

Each story follows the same shape and must meet this checklist:

- Every Endpoint subclass in the domain converts: `class Foo(Endpoint)` → `class Foo(AsyncEndpoint)`; `def execute(...)` → `async def execute(...)`; every `self.db.query(...)` → `await self.db.execute(select(...))`; every `self.database.find_by/create/update/...` → `await ...`.
- Router file for the domain **dual-registers**: async router at canonical path; sync handler code survives in-file for the observation window.
- Router flips `Depends(get_database)` → `Depends(get_async_database)` and `Depends(get_current_user)` → `Depends(get_current_user_async)` for every handler.
- Handler `return Foo.call(...)` → `return await Foo.call(...)`.
- Domain service (if any) converts in-place to async signatures.
- Domain event subscribers (if any) convert to async + register on the async dispatcher.
- **MCP tools for this domain** convert: `call_endpoint(...)` → `await call_endpoint_async(...)`; MCP tool file goes async alongside the domain.
- Test file converts: sync tests → async tests using `async_client`; `count_queries` assertions continue.
- **Lazy-load audit**: QA walkthrough lists every `selectinload` / `joinedload` used AND the grep output for the response-builder path showing every ORM attribute access is covered.
- **Baseline capture**: p50/p95 for every `normalized_path` in the domain (from `analyze_latency.py --window 24h` taken the day before the PR opens), plus client-observed p50/p95 from `client_latencies` for the same window.
- **Post-merge capture**: same numbers 24-48h after merge, AND (for low-traffic endpoints) a synthetic-load run using `tools/load_test_client_latencies.py` or equivalent.
- **Observation-window close**: story is not done until 24-48h in prod shows no p95 regression > 20% on any owned path. Only then does the sync handler code become eligible for `aam-24` deletion.

**`aam-10-meal-domain-async`** — Meal router + api + MealService + MCP meals tools. **Highest visibility** — owns the endpoint that started this epic.

ACs:
- `services/api/src/routers/v1/meal_router.py` + `services/api/src/api/v1/meal/*.py` (13 endpoints) + `libraries/utils/utils/services/meal_service.py` (500 LOC) + `services/api/src/mcp_server/tools/meals.py` all async.
- `hydrate_components` rewritten to `await` + `selectinload` (already uses selectinload; **lazy-load audit** verifies no implicit loads remain in the response-builder).
- `GET /v1/meals/{meal_id}` client-side p95 captured before + 24h after merge; **target < 500ms**.
- 13 test files in `services/api/tests/test_meal_*.py` convert to `async_client`.
- QA walkthrough includes: meal create + read + update + add-recipe + remove-recipe + reorder + favorite + share + archive + restore paths. MCP `remove_recipe_from_meal` + `archive_meal` confirmation gates still fire correctly.

**`aam-11-recipe-book-domain-async`** — recipe_book router + api + WebSocket + MCP recipe_books tools.

ACs:
- All recipe_book endpoints + MCP tools async.
- `recipe_book/websocket.py` handler accepts `AsyncSession`; query loop uses `await`; no sync-in-async during `websocket.send_text(...)` yields.
- **WS regression probe**: QA walkthrough exercises connect → subscribe → receive → disconnect → reconnect burst (10 connects in 2s) with `get_current_user_async` in the upgrade dep chain.

**`aam-12-recipe-domain-async`** — recipe router + api + MCP recipes tools.

ACs:
- All recipe endpoints async; recipe forking / versioning paths verified for lazy-load traps (version history has deep relationship chains — explicit audit).
- `pbq-3` fast-path (bulk favorite join from `list_recipes.py:82–94`) preserved.
- QA walkthrough: `GET /v1/recipes`, `GET /v1/recipes/{id}`, fork, version-history, restore.

**`aam-13-shopping-list-domain-async`** — shopping_list router + api + WebSocket + subscriber + MCP shopping tools.

ACs:
- `services/api/src/routers/v1/shopping_list_router.py` + `services/api/src/api/v1/shopping_list/*.py` all async.
- `shopping_list/websocket.py` → async session; broadcast loop uses `await`.
- Domain subscriber `shopping_list_subscriber` converts to async AND registers on the async dispatcher; worker-path subscribers (if any overlap) stay sync on the sync dispatcher.
- QA walkthrough: add/check-off items, WS broadcast (multi-client reconnect burst), `populate-from-recipe`, archive.

**`aam-14-calendar-and-meal-event-domain-async`** — calendar + meal_event + recurrence_rule routers + api + MCP meal_planning tools.

ACs:
- Three routers + all endpoints async.
- `list_calendars` member-count subquery (pbq-locked) preserved.
- QA walkthrough: calendar CRUD, meal-event CRUD (incl. XOR check), list views, recurrence-rule CRUD.

**`aam-15-pantry-domain-async`** — pantry router + PantryService + subscriber.

ACs:
- PantryService (289 LOC, 3 commits) converts in-place.
- `pantry_meal_subscriber` converts to async + registers on async dispatcher.
- Pantry CRUD + meal-event-completed → pantry-decrement flow tested end-to-end (verifies subscriber fires from async dispatcher path).

**`aam-16-activity-domain-async`** — activity router + ActivityService.

ACs:
- ActivityService (45 LOC, trivial) + activity endpoints async.
- `list_activities` cursor-less path (`pbq-5` contract) still drops `total=0`; grep re-verifies Flutter consumers before merge.
- QA walkthrough: Activity list mount, unread-count polling, see-all.

**`aam-17-search-domain-async`** — search router + unified_search + OpenAI embedding + MCP search tools.

ACs:
- Depends on `aam-7` (AsyncOpenAI swap).
- `unified_search` + `generate_recipe_embedding` + `assign_vibes_for_recipe` all async.
- `pbq-4a` memoization of `_get_my_book_ids()` preserved.
- QA walkthrough: text search, semantic search, filter combos.

**`aam-18-import-job-domain-async`** — import_job router + api + MCP import tools (incl. boto3 presign).

ACs:
- Depends on `aam-9` (boto3 threadpool wrap).
- Every import_job endpoint async; `GET /v1/import-jobs/{job_id}/items` (15587 samples/24h — heaviest endpoint in the system by volume) migrates with particular care.
- **Synthetic-load post-merge check**: because this endpoint has real traffic, the 24h window is enough; no synthetic supplement needed.
- QA walkthrough: share-extension flow, URL import, photo import.

**`aam-19-user-profile-push-tokens-async`** — user + profile + friends + push-tokens + MCP user tools.

ACs:
- Depends on `aam-8` (Firebase threadpool wrap).
- `GET /v1/users/me`, `POST /v1/users/me/push-tokens`, profile edit, friends endpoints all async.
- QA walkthrough: login (via Auth0 already-async), profile update, push-token register.

**`aam-20-admin-domain-async`** — admin router + all admin endpoints + MCP agent tools.

ACs:
- `GET /v1/admin/stats`, `GET /v1/admin/metrics/*` (client latency dashboards — high-volume), `/v1/admin/notifications/health/*` all async.
- Admin MCP tools + `mcp_server/tools/agent_tools.py` async.
- QA walkthrough: admin dashboard loads, all charts populate.

**`aam-21-misc-small-routers-async`** — feedback, client-errors, client-latencies, auth, health, notifications, flags, timer, units, chat, invitations, invite_links, cooking_log, parser + any router not owned by Phase 3 stories 10-20.

ACs:
- `POST /v1/users/me/client-errors` — p95 5931ms today — becomes async; expected to see the biggest single tail-latency improvement in the epic. **Target: server-side p95 < 200ms.**
- `POST /v1/client-latencies` (cla-1b), `/v1/feedback`, `/v1/flags/perf`, `/v1/notifications/*`, `/v1/chat/*`, `/v1/invitations/*`, `/v1/invite-links/*`, `/v1/cooking-logs/*`, `/v1/timer/*`, `/v1/units/*`, `/v1/parser/*` all async.
- QA walkthrough includes the client-errors and client-latencies ingest paths under synthetic load (reuses `tools/load_test_client_latencies.py`).

### Phase 4 — Middleware + lifespan (2 stories)

**`aam-22-error-tracking-middleware-async`** — bridge sync error logger via threadpool.

ACs:
- `services/api/src/middleware/error_tracking.py` keeps its sync `Database()` for the error-log write but invokes it via `await run_in_threadpool(self._log_error, ...)`.
- No sync DB call on the event loop in the middleware hot path.
- Sync error-log Database uses the dedicated 3-connection sub-pool from `aam-3` (not the main sync pool).
- Test: middleware test suite stays green with the async wrap; added test asserts no main-pool checkout happens during error-log writes.

**`aam-23-lifespan-and-pre-warm`** — async engine init + dispose, unit-alias pre-warm, prepared-statement warm-up.

ACs:
- Lifespan creates async engine on startup; disposes on shutdown (ordering: sync first on startup, async-then-sync on shutdown — see `aam-1`).
- Unit-alias cache pre-warm at `main.py:35` stays sync (standalone, one-shot); invoked once synchronously before the first request.
- **Prepared-statement warm-up**: on startup, fire a trivial `SELECT 1` on each async pool connection (up to `pool_size`) to prime asyncpg's prepared-statement cache. Blocks health-check green signal until complete. Expected added startup time: < 500ms for 20 connections.
- Healthcheck `/v1/health` unchanged — flips green only after pre-warm completes.
- Test: lifespan test validates warm-up runs and completes within a 5s budget.

### Phase 5 — Cutover (1 story)

**`aam-24-cutover-and-shim-removal`** — flip last holdouts, delete sync handler code, shrink sync pool.

ACs:
- All Phase 3 stories have closed their observation window green (no >20% p95 regression on any owned path).
- Any router still using `get_database` or `get_current_user` (sync) flips to async.
- **Sync handler code removal**: after observation windows closed green, every domain's sync handler file is deleted (Endpoint subclasses + their sync imports from routers).
- Sync `Endpoint` class: **kept** in `libraries/utils/utils/api/endpoint.py` (used by worker + scripts) but marked with a module-level assertion that fails loudly if imported from `services/api/src/api/v1/**/*.py`.
- Sync `get_database` + `get_current_user` in `services/api/src/dependencies.py` marked `_deprecated` with an import-time warning from API code. Still callable from `manage.py` + whitelisted paths.
- Sync MCP `get_current_database` + `call_endpoint` removed; only async variants remain in MCP scope.
- **Pool shrink PR** (separate commit inside the story): `DB_POOL_SIZE` 10 → 5, `DB_MAX_OVERFLOW` 20 → 10. Sync engine retains 15-connection headroom for the whitelisted paths. Total API peak now 75 → 35 connections; RDS headroom regained (at `max_connections=100`: 35 API + 15 beat/worker/migrator + 50 headroom).
- Full `analyze_latency.py --window 24h --section all` snapshot taken pre-cutover + 24h post-cutover. Every endpoint's p95 expected to be flat or improved.
- `GET /v1/meals/{meal_id}` client-side p95 (from `client_latencies`) verified < 500ms for 24h post-cutover before marking story done.
- Rollback commit hash documented in the QA walkthrough. **Rollback for `aam-24` itself is non-trivial** (sync handler code is gone) — the runbook's rollback-post-cutover section calls this out and names the last-good commit from before deletion as the baseline to re-apply.

### Phase 6 — Post-cutover hardening (3 stories)

**`aam-25-sync-in-async-startup-guard`** — fail-fast guard against regressions.

ACs:
- `main.py` startup registers an import-time check that walks the API's handler import graph and asserts no module under `services/api/src/api/v1/**/*.py` or `services/api/src/routers/v1/**/*.py` imports `from utils.services.database import Database` (sync).
- Whitelist: `services/api/src/middleware/error_tracking.py`, `services/api/src/middleware/latency_capture.py` (via writer), `services/api/src/main.py` (unit-alias pre-warm + error-log sub-pool init), `services/api/src/manage.py`.
- Test: hand-crafted regression — add a sync import to an API handler file and assert startup raises.
- CI wiring: the guard runs as part of `npx nx run api:test` so broken-at-merge-time regressions fail CI, not just prod startup.

**`aam-26-latency-baseline-snapshot`** — confirm the win (with tightened exit criteria).

ACs:
- `bin/prod-script services/api/scripts/analyze_latency.py --window 7d --section all` output captured pre-aam-1 (baseline snapshot saved as `_bmad-output/implementation-artifacts/aam-26-baseline.csv` the day `aam-1` opens) + 7 days post-`aam-24`.
- **Target 1**: `GET /v1/meals/{meal_id}` client-side p95: baseline 5192ms → target **< 500ms**. Hard gate.
- **Target 2**: `POST /v1/users/me/client-errors` server-side p95: baseline 5931ms → target **< 200ms**. Hard gate.
- **Target 3**: no other endpoint's p95 regressed > 20%. If any did, the story does not close — a follow-up aam-28+ fix is filed and becomes blocking.
- **Target 4**: `POST /v1/client-latencies` ingest endpoint (cla-1b path) p95 unchanged or improved.
- All endpoints' server-side p95 deltas tabulated in `_bmad-output/implementation-artifacts/aam-26-qa-walkthrough.md` with sample-count alongside p95 (so low-traffic noise is visible).
- If targets 1 or 2 are missed → story blocks on investigation; rollback to last-good commit pre-`aam-24` is an option explicitly on the table.

**`aam-27-concurrent-load-integration-test`** — regression test that the event loop isn't held (sharpened proxy).

ACs:
- New integration test under `services/api/tests/integration/test_async_non_blocking.py`.
- Test uses **a real slow-query shape** as the proxy, not just `asyncio.sleep`: seeds ~1000 meals into the test DB; fires `GET /v1/meals` (which hits DB) concurrently with `GET /v1/health` (trivial) and asserts the health check's wall-clock stays < 50ms while the meals list is in flight.
- **Secondary scenario**: patches `OpenAI` embedding call to sleep 3s (realistic external-API proxy); fires `POST /v1/search` concurrently with `GET /v1/health`; asserts health < 50ms. Covers the "external slow call holds event loop" regression that the draft's pure-`asyncio.sleep` proxy missed.
- CI-enforced. If the test is disabled or weakened, CI fails.
- Documented in `docs/async-migration-runbook.md` as the canonical "is the async migration still doing its job?" signal.

### CUT stories (party-mode 2026-04-23)

None. All 27 draft stories survive party-mode; 6 were renamed/expanded to absorb newly-scoped work (MCP tools, worker contract gate, RDS capacity, cold-start pre-warm, lazy-load audits, sharpened integration test).

## Dependencies

**Cross-story within this epic:**
- `aam-1` blocks every downstream story (includes RDS parameter-group change).
- `aam-2`, `aam-3`, `aam-4` block Phase 2 + Phase 3.
- `aam-6` blocks every Phase 3 story (they all flip `get_current_user` → async).
- `aam-7` blocks `aam-17`.
- `aam-8` blocks `aam-19`.
- `aam-9` blocks `aam-18`.
- All Phase 3 stories parallelize once Phase 1 is done.
- Phase 4 parallel with late Phase 3.
- `aam-24` requires all Phase 2 / 3 / 4 stories merged AND all Phase 3 observation windows closed green.
- Phase 6 requires `aam-24`.

**Cross-epic:**
- **New (party-mode):** shares `services/worker/tests` + `services/parser/tests` CI gating with those service epics. `aam-2` and `aam-4` explicitly re-run those suites; breakage blocks merge.
- **New (party-mode):** terraform coordination — `aam-1`'s RDS parameter-group change touches `terraform/modules/rds/parameter_group.tf`; confirm no in-flight `epic-perf-infra-and-measurement` or android CI epic has a conflicting parameter-group change. As of 2026-04-23 the `pim-*` epic landed and is done — no conflict expected.
- Reads from `epic-perf-client-analytics` (`cla-*`) for the client-latency dashboard — the metric surface for validating the win.
- Reads from `epic-perf-debug-tooling` (`ptd-6`) for `analyze_latency.py --regression-hunt` — regression guardrail during rollout.
- Respects `epic-perf-backend-query-tuning` locked design principles (selectinload for 1-to-many, memoization scope, no joinedload on fanouts). The `count_queries` rewrite preserves every existing `pbq-*` assertion.
- Does **not** conflict with `epic-observability-latency` — request_latencies middleware is already async; continues to work unchanged.
- Does **not** conflict with `epic-ios-native`, `epic-android-play-console-launch`, `epic-calendars-*`, or any in-flight product epics (response shapes unchanged; Flutter code untouched).

## Open Questions for the User

**Party-mode-surfaced (new):**

1. **RDS reboot window for `aam-1`.** Raising `max_connections` to 100 requires a reboot of the RDS instance. Options:
   - **(a) Reboot during deploy**: ~30s unavailability on API (ECS holds connections, reconnects cleanly); app users see a brief 502 spike. Ship during 2am–6am UTC to minimize impact.
   - **(b) Skip the raise**: keep `max_connections=60`, make the async pool smaller (15/25 instead of 20/40). Tighter budget but no reboot needed. Risk: at ~50 simultaneous requests the async pool exhausts; request queueing returns (different failure mode than today, but same user-visible symptom).
   - **Default planned**: (a), 3am UTC, ship same week as `aam-1`. Override if you want to pick a specific night.

2. **Observation-window length.** Between per-domain merge and sync handler code deletion. Draft said 24-48h. At our traffic (~single-user) 48h may still not accumulate enough samples on rarely-hit endpoints for a confident delta. Options:
   - **(a) 48h fixed**: ship quickly, accept that cold-path endpoints get thin evidence.
   - **(b) Traffic-conditional**: domain closes once it has ≥100 samples per owned path post-merge, capped at 7 days.
   - **Default planned**: (a) 48h fixed + synthetic-load supplement per story's Phase 3 AC list. Override if you want (b).

3. **MCP tool test coverage during dual-dispatch.** During a Phase 3 story's observation window, MCP tools for that domain call `call_endpoint_async(...)`. If the async endpoint has a bug, MCP-triggered calls fail silently-ish (AI just gives a weird answer rather than a 500 the user sees). Worth adding explicit MCP smoke tests per domain post-merge? Cost: ~30min per story. Default planned: **yes** — each Phase 3 story runs its MCP tools via `services/api/src/mcp_server/client.py` against staging once, pastes output in QA walkthrough.

4. **Worker contract freeze end-date.** The sync `Database` public API is frozen for the duration of the epic. Some upcoming work (e.g. if a later epic wants to rename `find_or_create_by` for clarity) gets blocked. Worth scheduling a "post-async cleanup" epic that unlocks the sync-API in one sweep after `aam-27` closes? Default planned: **yes**, file a placeholder `epic-async-migration-cleanup` for post-aam-27 — it can batch the sync API tweaks + consider whether to rename `AsyncEndpoint` → `Endpoint` (see next question).

**Pre-drafted (carried from draft):**

5. **Dual Endpoint class naming after cutover.** Post-cutover, rename `AsyncEndpoint` → `Endpoint` (mass rename across ~194 subclasses, cleaner final state) or keep `AsyncEndpoint` permanently in the API scope (less churn, slightly awkward name)? Default planned: **keep `AsyncEndpoint`** for this epic; defer the rename to the cleanup epic from Q4.

6. **Rollout cadence.** The 12 Phase 3 stories could all merge in one sprint by parallelizing `/dev` loops. Or merge one per day and watch deltas. Default planned: **staggered — land foundations + SDK swaps week 1, then 2–3 Phase 3 stories per day over week 2, observation windows overlap, cutover end of week 2 + 48h**. Overrideable.

7. **Canary.** Worth spending ~half a day on a weighted target group before `aam-24`? At single-user today the answer is probably no, but the observation-window pattern (party-mode addition) effectively provides per-domain canarying already. Default planned: **skip — the observation window is the canary**.

8. **`bin/prod-script` prelude: refactor or leave alone?** The prelude imports `from utils.services.database import Database` and continues to work because `Database` (sync) survives. Could add `AsyncDatabase` injection for future async ops scripts. Default planned: **leave alone; ops scripts keep sync access**. Revisit if a real async ops script use case arises.
