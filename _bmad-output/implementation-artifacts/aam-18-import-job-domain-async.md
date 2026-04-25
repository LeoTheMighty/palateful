# aam-18 — Import Job Domain Async

**Epic:** [epic-api-async-migration](../planning-artifacts/epic-api-async-migration.md)
**Status:** in-progress
**Prerequisites landed:** aam-1..aam-6 (foundations), aam-9 (boto3 threadpool wrap — `_async` twins on `AWSService`), aam-foundations-notify-threadpool-helper.

## Scope

Convert the import_job domain from sync `Endpoint` to `AsyncEndpoint`, matching the recipe in
`_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md`. Heaviest domain in the system
by volume — `GET /v1/import-jobs/{job_id}/items` alone is 15587 samples / 24h (per epic
D-08 note).

**Files in scope:**

- Endpoints (20 classes, all become `AsyncEndpoint`):
  - `services/api/src/api/v1/import_job/approve_import_item.py` — `ApproveImportItem`
  - `services/api/src/api/v1/import_job/archive_import_item.py` — `ArchiveImportItem`
  - `services/api/src/api/v1/import_job/cancel_import_job.py` — `CancelImportJob`
  - `services/api/src/api/v1/import_job/dismiss_all_failed_imports.py` — `DismissAllFailedImports`
  - `services/api/src/api/v1/import_job/dismiss_import_item.py` — `DismissImportItem`
  - `services/api/src/api/v1/import_job/get_import_item.py` — `GetImportItem`
  - `services/api/src/api/v1/import_job/get_import_item_telemetry.py` — `GetImportItemTelemetry`
  - `services/api/src/api/v1/import_job/get_import_job.py` — `GetImportJob`
  - `services/api/src/api/v1/import_job/get_upload_url.py` — `GetImportUploadUrl` (boto3 presign)
  - `services/api/src/api/v1/import_job/list_import_items.py` — `ListImportItems` (hottest endpoint)
  - `services/api/src/api/v1/import_job/list_import_items_batch.py` — `ListImportItemsBatch`
  - `services/api/src/api/v1/import_job/list_import_jobs.py` — `ListImportJobs`
  - `services/api/src/api/v1/import_job/list_see_all_items.py` — `ListSeeAllImportItems`
  - `services/api/src/api/v1/import_job/retry_import_item.py` — `RetryImportItem`
  - `services/api/src/api/v1/import_job/see_all_count.py` — `ImportSeeAllCount`
  - `services/api/src/api/v1/import_job/skip_import_item.py` — `SkipImportItem`
  - `services/api/src/api/v1/import_job/start_import.py` — `StartImport` (boto3 head_object)
  - `services/api/src/api/v1/import_job/submit_correction.py` — `SubmitCorrection`
  - `services/api/src/api/v1/import_job/unarchive_import_item.py` — `UnarchiveImportItem`
  - `services/api/src/api/v1/import_job/update_import_item.py` — `UpdateImportItem`
- Helper: `services/api/src/api/v1/import_job/counters.py` — shared counter query helpers, converted to `async def`.
- Router: `services/api/src/routers/v1/import_router.py` — all 20 handlers become `async def` with `get_current_user_async` + `get_async_database` + `await X.call(...)`.
- MCP tool: `services/api/src/mcp_server/tools/import_tools.py` — 3 tools (`import_recipe`, `get_import_status`, `approve_import`) become `async def` and dispatch through `await call_endpoint_async(...)`.
- Tests (5 files, all rewritten to `mock_async_db` + `MockExecuteResult`):
  - `services/api/tests/test_import.py` (5651 LOC — the bulk)
  - `services/api/tests/test_import_failed_transitions.py`
  - `services/api/tests/test_import_notifications.py`
  - `services/api/tests/test_import_telemetry.py`
  - `services/api/tests/mcp_server/test_import_tools.py`

**Explicitly NOT in scope:**

- `utils/services/aws.py` — `AWSService` class. Sync methods stay for the worker / scripts; endpoints consume the `_async` twins added in aam-9.
- `utils/tasks/import_tasks/parse_source_task.py` and the other Celery task modules — worker-side, still sync.
- `utils/services/recipe_extractors/*` (pdf, audio, spreadsheet helpers invoked inline in `StartImport`) — heavy CPU/IO that doesn't ship on the request path very often. Wrap in `run_in_threadpool` where called from async so the event loop stays free, but don't rewrite the helpers themselves.
- `StartImport`'s dispatch to `parse_source_task.delay(...)` — Celery broker call is sync but non-blocking (pushes to Redis). Keep sync.

## Approach

### Endpoint classes

Every `class X(Endpoint)` → `class X(AsyncEndpoint)`. `def execute` → `async def execute`.
Every `self.db.query(...)` / `self.database.find_by(...)` / `self.database.create(...)`
/ `self.database.db.commit()` etc. converts per the cheat-sheet in
`aam-phase1-dev-snippets.md`.

**Boto3 calls** (in `start_import.py` + `get_upload_url.py`): swap
`_get_aws_service().presign_put_url(...)` → `await _get_aws_service().presign_put_url_async(...)`
and `head_object` → `head_object_async`. These `_async` twins were added in aam-9.

**Inline sync helpers** in `StartImport.execute` for PDF/audio/spreadsheet parsing
(`transcribe_audio`, `classify_pdf`, `extract_text_from_pdf`, `parse_spreadsheet`) —
keep the calls but wrap each in `await run_in_threadpool(fn, *args)` so the event loop
stays free during heavy CPU/IO.

**Celery dispatch** — `parse_source_task.delay(...)` stays sync (pushes to Redis
synchronously but does not block on task completion — matches the existing pattern in
aam-11 through aam-17 for Celery `.delay()` calls).

**`counters.py`** — private helpers `_get_see_all_counts(...)`, etc. become `async def`
and `await self.db.execute(...)` internally. Callers (`ImportSeeAllCount`,
`ListSeeAllImportItems`, `DismissAllFailedImports`) await them.

### Router flip

`import_router.py` — every handler flips from sync `def` (Phase 0 shim) to `async def`
with:
- `user: User = Depends(get_current_user_async)`
- `database: AsyncDatabase = Depends(get_async_database)`
- `return await X.call(...)`

### MCP tool flip

`mcp_server/tools/import_tools.py` — 3 tools (`import_recipe`, `get_import_status`,
`approve_import`) become `async def` and dispatch through `await call_endpoint_async(...)`.
Helper `_build_start_import_params`, `_require_default_book` stay sync.

### Tests

All 5 test files switch from `mock_db` to `mock_async_db` and replace
`MockQuery(...)` return values with `MockExecuteResult(items=[...])` via
`side_effect = [...]`. Count `await self.db.execute(...)` + `await self.database.find_by(...)`
+ `await self.database.where(...).all()` in each endpoint to size each `side_effect`
list. Preserve every test name and assertion; no deletions.

MCP test (`test_import_tools.py`) — patch `mcp_server.tools.import_tools.call_endpoint_async`
with `new_callable=AsyncMock` and `await` each tool.

## Acceptance Criteria

- [ ] Every class in `services/api/src/api/v1/import_job/*.py` inherits `AsyncEndpoint`; every `self.db` / `self.database` call uses `select()` + `await` or `await` on find_by/create/update/delete.
- [ ] `counters.py` helpers are `async def` and awaited.
- [ ] `import_router.py` — every handler is `async def` using `get_current_user_async` + `get_async_database` + `return await X.call(...)`.
- [ ] `mcp_server/tools/import_tools.py` — 3 tools are `async def` and call `await call_endpoint_async(...)`.
- [ ] `start_import.py` + `get_upload_url.py` use `AWSService._async` variants (`presign_put_url_async`, `head_object_async`). Heavy CPU helpers (`transcribe_audio`, `classify_pdf`, `extract_text_from_pdf`, `parse_spreadsheet`) invoked via `run_in_threadpool`.
- [ ] All 5 test files rewritten to `mock_async_db` shape; every test name preserved; no test deletions.
- [ ] `npx nx run api:lint` green.
- [ ] `npx nx run api:test` green with 100% coverage.
- [ ] sprint-status: `aam-18-import-job-domain-async: backlog` → `review` → `done`.

## Out-of-Scope Callouts / Gotchas

- `_get_aws_service()` singleton caches an `AWSService` instance module-level; both sync and async variants live on the same instance, so the singleton stays.
- `StartImport.execute` is 420+ LOC with many branches. Convert the whole method at once — do not half-convert. The try/except IntegrityError + rollback patterns become `async with` / `await self.database.db.rollback()`.
- `_check_rate_limit` / `_reset_rate_limit_for_test` are pure in-memory helpers (no DB); stay sync.
- `_find_existing_job` on `StartImport` uses a sync `.query(...)` currently — becomes `async def` with `await self.db.execute(select(...).limit(1))`.
- `_validate_s3_key_inputs` on `StartImport` calls `aws.head_object` + a dedupe DB query — becomes `async def` awaiting `head_object_async` and the select.
- `retry_import_item.py` — dispatch callbacks `_dispatch_parse`, `_dispatch_extract`, `_dispatch_create` call Celery `.delay(...)` only; stay sync, called from the `async def execute`.
- `dismiss_import_item.py`, `archive_import_item.py`, `unarchive_import_item.py` — status-guard patterns (`if item.status == "in_progress": raise`) are pure in-memory checks; only the fetch + update use async DB.
- `approve_import_item.py` — creates a Recipe via `await self.database.create(recipe)`, then updates ImportItem status via `await self.database.update(item, status="approved")`. Fan-out to `create_recipe_task.delay(...)` stays sync. No notification here — notifications fire from the worker when the Recipe finishes.
- `test_import.py` at 5651 LOC is the bulk of the test work. Expected pattern: per-test, read the endpoint's `execute`, count the async DB calls, rebuild `mock_async_db.db.execute.side_effect` in order.
- Memoization inside endpoints (cached `self._my_book_ids`-style attrs): none in this domain.

## QA Walkthrough

See `aam-18-qa-walkthrough.md` (generated alongside this story).
