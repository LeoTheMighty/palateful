---
hash: aam27
type: dev
created: 2026-07-27T17:19:00-06:00
title: Concurrent-load integration test — CI-enforced proof the event loop is never held
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: ready
blocked-by: [aam24]
branch: feat/dev-aam27
---

## Goal
Add the canonical "is the async migration still doing its job?" regression test: an integration test that runs a realistically slow request (real DB fan-out, and a patched slow external OpenAI call) concurrently with `GET /v1/health` and asserts the health check's wall-clock stays fast, proving no handler holds the event loop.

## Acceptance criteria
- [ ] New integration test at `services/api/tests/integration/test_async_non_blocking.py`.
- [ ] Primary scenario uses a real slow-query shape, not bare `asyncio.sleep`: seed ~1000 meals into the test DB; fire `GET /v1/meals` concurrently with `GET /v1/health` and assert health wall-clock < 50ms while the meals list is in flight.
- [ ] Secondary scenario: patch the OpenAI embedding call to sleep 3s; fire `POST /v1/search` (unified search) concurrently with `GET /v1/health`; assert health < 50ms — covers the "slow external call holds the loop" regression.
- [ ] CI-enforced: runs as part of `npx nx run api:test`; disabling or weakening the test fails CI.
- [ ] Documented in `docs/async-migration-runbook.md` (landed in aam-5, commit `671a74e`) as the canonical non-blocking regression signal.
- [ ] Coverage stays at 100%.

## Technical notes
- Epic Phase 6 story `aam-27-concurrent-load-integration-test`. Snippets: CHUNK-C8 in `aam-phase1-dev-snippets.md` (proposes a 50-concurrent-request p95-multiple variant; the epic's party-mode version — health-latency-under-concurrent-slow-work — is the sharper, less flaky assertion; follow the epic).
- Verification against main (2026-07-27): NOT landed — `services/api/tests/integration/` does not exist. Fixtures needed are in place: `async_client` (httpx `ASGITransport`) from aam-4 (commit `e85d04a`), async test engine in `libraries/test_helper/async_db.py`.
- Secondary-scenario patch point: the OpenAI call lives in `services/api/src/api/v1/search/unified_search.py` — after aam-7 it's an `AsyncOpenAI` call; patch it with an `async` sleep-then-return stub. If aam-7 somehow hasn't landed first, patch the `run_in_threadpool`-bridged sync fn with `time.sleep(3)` — the test must pass either way post-aam-24 (threadpool version also keeps the loop free; the assert still holds).
- Timing asserts in CI can flake; use a monotonic clock, generous seeding timeout, and consider 2-3 retries on the 50ms bound only if CI machines prove noisy — but do not raise the bound silently (AC forbids weakening).
- Blocked-by aam-24 per epic phase ordering (Phase 6 requires cutover); in practice the test could pass earlier since all domains are async on main, but post-cutover is when it becomes the permanent guard.
- Original BMAD story key: aam-27-concurrent-load-integration-test.

## Status log
- 2026-07-27T17:19 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
