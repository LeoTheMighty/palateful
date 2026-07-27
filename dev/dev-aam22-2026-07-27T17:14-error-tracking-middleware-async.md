---
hash: aam22
type: dev
created: 2026-07-27T17:14:00-06:00
title: Error-tracking middleware — bridge the sync error-log write off the event loop via threadpool and the dedicated error-log sub-pool
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: ready
blocked-by: []
branch: feat/dev-aam22
---

## Goal
`ErrorTrackingMiddleware.dispatch` currently calls the sync `_log_error` (which opens a sync `Database()` on the main sync pool) directly on the event loop. Wrap the write in `await run_in_threadpool(...)` and point it at the dedicated 3-connection error-log sub-pool that aam-3 already shipped, so an error burst can never block the loop or contend with the main pools.

## Acceptance criteria
- [ ] `services/api/src/middleware/error_tracking.py` keeps its sync `Database()` for the error-log write but invokes it via `await run_in_threadpool(self._log_error, ...)` on both paths (unhandled-exception at line ~28 and 500-response at line ~38).
- [ ] No sync DB call on the event loop remains in the middleware hot path.
- [ ] The sync error-log `Database` uses the dedicated error-log sub-pool from aam-3 (`utils.services.database.error_log_engine` / `ErrorLogSessionLocal`), not the main sync pool — same pattern `AsyncEndpoint._log_error_to_db_async` uses (`libraries/utils/utils/api/endpoint.py:432-444`).
- [ ] Middleware test suite stays green with the async wrap; added test asserts no main-pool checkout happens during error-log writes.
- [ ] Coverage stays at 100%.

## Technical notes
- Epic Phase 4 story `aam-22-error-tracking-middleware-async`. Snippets: CHUNK-C2 in `aam-phase1-dev-snippets.md` — "Flip to `run_in_threadpool`-wrapped `Database(db=ErrorLogSessionLocal())` pattern (already how `AsyncEndpoint` does it)."
- Verification against main (2026-07-27): NOT landed. `error_tracking.py:28` and `:38` call `self._log_error(...)` synchronously; `:65` constructs a plain `Database()` on the default sync pool. The prerequisite sub-pool from aam-3 exists and is proven (`endpoint.py:311-314` comment: "prefer the dedicated error-log engine (pool_size=3...)"), so this is a small, self-contained change.
- Snippets also list `services/api/src/middleware/latency_capture.py` in the chunk file list — it writes via the batched daemon-thread writer (whitelisted per design principle 1); verify and document, don't rewrite.
- Parallel-safe with aam-7/aam-8/aam-23; required before aam-24 (epic dependency: aam-24 needs all Phase 4 merged).
- Original BMAD story key: aam-22-error-tracking-middleware-async.

## Status log
- 2026-07-27T17:14 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
