---
hash: aam22
type: dev
created: 2026-07-27T17:14:00-06:00
title: Error-tracking middleware — bridge the sync error-log write off the event loop via threadpool and the dedicated error-log sub-pool
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
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
- 2026-07-28T10:11:42-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-28T16:25:10.872Z — loop iteration 1: Moved ErrorTrackingMiddleware's error-log writes off the event loop via run_in_threadpool onto the aam-3 error-log sub-pool, with full test coverage including a no-main-pool-checkout assertion.
  - Change: error_tracking.py: both dispatch error paths (unhandled exception, 5xx response) now await run_in_threadpool(self._log_error, ...) instead of calling it on the event loop
  - Change: error_tracking.py: _log_error now writes via Database(db=ErrorLogSessionLocal()) on the dedicated aam-3 error-log sub-pool, with the same None-fallback guard AsyncEndpoint uses
  - Change: error_tracking.py: stack trace derived via traceback.format_exception(error) instead of format_exc(), since sys.exc_info() is empty on the threadpool worker thread and format_exc() would record 'NoneType: None'
  - Change: test_error_tracking.py: 5 new tests — threadpool dispatch asserted on both paths, sub-pool session selection, default-pool fallback, and no-main-pool-checkout during writes (real Database, mocked session factories); error_tracking.py at 100% line+branch coverage, lint and silent-catch guard green
  - Learning: Main CI is deliberately red: commit 5a6174de 'plan: rotation-self-heal — red stage' committed test_health.py tests importing a nonexistent utils.services.db_probe module (17 errors + 1 failure + 3 uncovered lines in health_router.py, overall coverage 99.98%). Every full-suite failure on this branch is that pre-existing red-stage, owned by another item — any Phase 4 merge will hit this in CI until rotation-self-heal lands.
  - Learning: endpoint.py's _log_error_to_db also uses traceback.format_exc() despite being run via run_in_threadpool — it likely records 'NoneType: None' stack traces in production; possible small follow-up fix in libraries/utils.
  - Learning: Fresh devx worktrees need `npx nx run api:install` and an explicit DATABASE_URL to run the api suite; the CI-matching URL postgresql://postgres:postgres@localhost:5432/test works against the leftover debug-e2edwds docker postgres, which already has a 'test' database.
