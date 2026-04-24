# aam-29 — Parser Domain Async

**Epic:** [epic-api-async-migration](../planning-artifacts/epic-api-async-migration.md)
**Status:** done
**Prerequisites landed:** aam-1..aam-6 (foundations), aam-9 (boto3 async variants on
`AWSService`), aam-10 (meal reference), aam-foundations-notify-threadpool-helper.

## Scope

Convert the parser domain from sync `Endpoint` to `AsyncEndpoint` +
`get_async_database` + `get_current_user_async`, matching the recipe in
`_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md`. Per chunk D-12: the
boto3 callsites use the `*_async` variants on `AWSService` (already landed in
aam-9); this chunk does the endpoint → AsyncEndpoint + router flip only.

**Files in scope:**
- Endpoints (`services/api/src/api/v1/parser/`):
  - `get_upload_url.py` — `GetUploadUrl`.
  - `submit_parser_job.py` — `SubmitParserJob`.
  - `submit_batch_parser_job.py` — `SubmitBatchParserJob`.
  - `get_parser_job.py` — `GetParserJob` (plus `_sync_batch_status` → `_sync_batch_status_async`).
  - `create_parser_batch.py` — `CreateParserBatch`.
  - `get_parser_batch.py` — `GetParserBatch`.
  - `list_parser_batches.py` — `ListParserBatches`.
  - `complete_parser_batch.py` — `CompleteParserBatch` (hybrid: async outer / threadpool inner).
- Router: `services/api/src/routers/v1/parser_router.py` — 8 handlers flipped to `async def`.
- Tests: `services/api/tests/test_parser.py`, `services/api/tests/test_parser_batches.py` —
  rewritten to `mock_async_db` / `MockExecuteResult` patterns.

**Explicitly NOT in scope:**
- `libraries/utils/utils/services/parser_batch_completion.py` — sync helper shared with
  `WatchParserBatchTask` (celery worker). Left sync; the callback endpoint dispatches it
  via `run_in_threadpool` with a fresh sync `Database(db=SessionLocal())`. The worker
  side stays on sync `Database` unchanged.
- `libraries/utils/utils/services/aws.py` — `*_async` variants already landed in aam-9;
  no further work needed here.
- MCP tools — no parser domain MCP tool exists (parser endpoints are UI-only).

## Approach

### Endpoint classes

Each endpoint:
1. Change base: `class X(Endpoint)` → `class X(AsyncEndpoint)`.
2. `def execute(...)` → `async def execute(...)`.
3. Translate DB calls per the cheat-sheet:
   - `self.database.create(obj)` → `await self.database.create(obj)`.
   - `self.database.db.commit()` → `await self.database.db.commit()`.
   - `self.database.db.refresh(obj)` → `await self.database.db.refresh(obj)`.
   - `self.database.find_by(Model, id=...)` → `await self.database.find_by(Model, id=...)`.
   - `self.database.db.query(Model).filter(...).first()` → `(await self.database.db.execute(
     select(Model).filter(...))).scalars().first()` (or use `self.database.where(...).first()`).
   - `self.database.db.query(Model).filter(...).all()` → `(await self.database.db.execute(
     select(Model).filter(...))).scalars().all()`.
4. Replace every sync `AWSService` method with its `*_async` variant:
   - `aws.generate_presigned_upload_url(...)` → `await aws.generate_presigned_upload_url_async(...)`.
   - `aws.submit_batch_job(...)` → `await aws.submit_batch_job_async(...)`.
   - `aws.submit_batch_manifest_job(...)` → `await aws.submit_batch_manifest_job_async(...)`.
   - `aws.describe_batch_job(...)` → `await aws.describe_batch_job_async(...)`.
   - `aws.get_s3_object(...)` → `await aws.get_s3_object_async(...)`.
   - `aws.map_batch_status_to_parser_status(...)` — pure function, stays sync.

### `CompleteParserBatch` hybrid

The callback endpoint delegates to `complete_parser_batch(db, aws, parser_batch)` —
a sync helper shared with `WatchParserBatchTask`. The helper does many DB reads +
writes + commits and dispatches celery tasks; rewriting it async would duplicate the
logic (worker still needs sync). So we:

1. Keep `CompleteParserBatch` as `AsyncEndpoint` / `async def execute(...)` to
   satisfy the chunk AC.
2. Inside `execute`, dispatch the entire sync workflow (load batch → call
   `complete_parser_batch(...)` → build response) via `run_in_threadpool` on a fresh
   `Database(db=SessionLocal())`. A helper module-level function `_run_complete_sync`
   encapsulates the threadpool body. 404 is raised inside the threadpool and surfaces
   through `AsyncEndpoint.run`'s normal `APIException` path.

This mirrors the `_bootstrap_default_list_sync` pattern from
`api/v1/user/complete_onboarding.py` (aam-19). Tests patch
`api.v1.parser.complete_parser_batch.SessionLocal` to return a mock session wrapping
the existing `mock_db` behavior.

### Router flip

`parser_router.py` — all 8 handlers flip to `async def` with
`Depends(get_current_user_async)` + `Depends(get_async_database)` + `return await
X.call(...)`. The `complete_parser_batch` handler is unauthenticated so it keeps
only the `database` dep.

### Tests

- Sync `mock_db.db.query.return_value = MockQuery([...])` patterns rewrite to the
  async shape:
  - `mock_async_db.db.execute.return_value = MockExecuteResult([...])` for single-row
    reads, or
  - `mock_async_db.db.execute.side_effect = [MockExecuteResult(...), ...]` for multi-
    read sequences.
- `mock_db.set_find_by(Model, obj, id=...)` patterns flip to
  `mock_async_db.set_find_by(Model, obj, id=...)`. `MockAsyncDatabase.set_find_by`
  honors both `find_by` and `where(...).first()` lookups, so handlers that access
  via either path get the same fixture.
- For `CompleteParserBatch` tests: patch `SessionLocal` inside the endpoint module
  and wire the returned session's `.query(ParserBatch)...` to the same `MockQuery`
  shape the sync tests used, so test intent is preserved.

Test class preservation: every test name and scenario stays; assertions only change
where the mock shape changes.

## Acceptance Criteria

- [ ] Every endpoint class in `services/api/src/api/v1/parser/` is `AsyncEndpoint`
  with `async def execute`.
- [ ] Every router handler in `parser_router.py` is `async def` using
  `get_current_user_async` + `get_async_database` + `await X.call(...)` (except
  the unauthenticated `complete_parser_batch` handler, which keeps only
  `get_async_database`).
- [ ] AWS SDK callsites use `*_async` variants exclusively (`generate_presigned_upload_url_async`,
  `submit_batch_job_async`, `submit_batch_manifest_job_async`, `describe_batch_job_async`,
  `get_s3_object_async`).
- [ ] `CompleteParserBatch` dispatches the sync `complete_parser_batch` helper via
  `run_in_threadpool` with a fresh `Database(db=SessionLocal())`.
- [ ] `test_parser.py` + `test_parser_batches.py` rewritten to the `mock_async_db` /
  `MockExecuteResult` pattern; every test name preserved; no deletions; 100% coverage
  on `services/api/src/api/v1/parser/*.py` and `services/api/src/routers/v1/parser_router.py`.
- [ ] `npx nx run api:lint` green.
- [ ] `npx nx run api:test` green with the 100% coverage gate.
- [ ] sprint-status: `aam-29-parser-domain-async: backlog` → `review` → `done`.

## Out-of-Scope Callouts / Gotchas

- `complete_parser_batch` (the sync helper) is shared with `WatchParserBatchTask` in
  the celery worker; it must stay sync. The hybrid dispatch pattern is the
  intentional trade-off.
- `map_batch_status_to_parser_status` is a pure mapping function — stays sync, called
  from async without `await`.
- Watcher celery tasks (`watch_parser_job_task`, `watch_parser_batch_task`) are still
  dispatched via `apply_async` / `delay` from async context — celery handles its own
  thread safety; no change needed.
- `_sync_batch_status` in `GetParserJob` renames to `_sync_batch_status_async` and
  becomes `async def`; every caller awaits. The side-effect pattern (mutate
  `parser_job` attributes in-place + `commit`) stays identical.

## Deliverables

- `_bmad-output/implementation-artifacts/aam-29-parser-domain-async.md` — this file.
- `_bmad-output/implementation-artifacts/aam-29-qa-walkthrough.md` — per-endpoint
  trace + test inventory + lazy-load audit.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip `aam-29-parser-
  domain-async` to `done`.
