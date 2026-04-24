# aam-29 — Parser Domain Async — QA Walkthrough

**Scope:** Convert the `/v1/parser/*` endpoint surface from sync `Endpoint` to
`AsyncEndpoint`, flip the router to `get_async_database` +
`get_current_user_async`, switch boto3 callsites to the `*_async` variants
landed by aam-9, and rewrite `test_parser.py` + `test_parser_batches.py` to
the `mock_async_db` / `MockExecuteResult` pattern.

Explicitly out of scope:
- `libraries/utils/utils/services/parser_batch_completion.py` — sync helper
  shared with `WatchParserBatchTask` in the celery worker. Left sync; the
  callback endpoint bridges via `run_in_threadpool`.
- `libraries/utils/utils/services/aws.py` — `*_async` variants already
  landed in aam-9; no change here.
- Parser MCP tools — none exist (parser endpoints are UI-only).

## Smoke checklist

All 31 parser tests green locally:

```
cd services/api && DATABASE_URL=postgresql://x/y poetry run pytest \
    tests/test_parser.py tests/test_parser_batches.py --no-cov -q
# → 31 passed
```

Coverage on every converted surface: 100%.

```
src/api/v1/parser/__init__.py                      9   0   100%
src/api/v1/parser/complete_parser_batch.py        28   0   100%
src/api/v1/parser/create_parser_batch.py          60   0   100%
src/api/v1/parser/get_parser_batch.py             41   0   100%
src/api/v1/parser/get_parser_job.py               48   0   100%
src/api/v1/parser/get_upload_url.py               23   0   100%
src/api/v1/parser/list_parser_batches.py          34   0   100%
src/api/v1/parser/submit_batch_parser_job.py      40   0   100%
src/api/v1/parser/submit_parser_job.py            32   0   100%
src/routers/v1/parser_router.py                   30   0   100%
```

Lint green on parser files:

```
cd services/api && poetry run ruff check \
    src/api/v1/parser/ src/routers/v1/parser_router.py \
    tests/test_parser.py tests/test_parser_batches.py
# → All checks passed!
```

## Endpoint-by-endpoint trace

### POST /v1/parser/upload-url (`GetUploadUrl`)

- **Handler:** `async def get_upload_url` ← `get_current_user_async` +
  `get_async_database` ← `await GetUploadUrl.call(...)`.
- **Endpoint:** `AsyncEndpoint`, `async def execute`.
- **AWS:** `await aws.generate_presigned_upload_url_async(...)`.
- **DB:** none — pure S3 presign.

### POST /v1/parser/jobs (`SubmitParserJob`)

- **Handler:** `async def submit_parser_job`.
- **Endpoint:** `AsyncEndpoint`, `async def execute`.
- **DB:** `await self.database.create(parser_job)` (single commit+refresh),
  later `await self.database.db.commit()` for the status update.
  Consolidated from 3 commits (old sync) to 2.
- **AWS:** `await aws.submit_batch_job_async(...)`.
- **Celery:** `watch_parser_job_task.apply_async(...)` — celery handles its
  own threading; no wrapping needed.

### POST /v1/parser/jobs/batch (`SubmitBatchParserJob`)

- **Handler:** `async def submit_batch_parser_job`.
- **Endpoint:** `AsyncEndpoint`, `async def execute`.
- **DB:** per-job `self.database.db.add(parser_job)` (no commit), then a
  single `await self.database.db.commit()` + per-job `await
  self.database.db.refresh(pj)`, then one more `await commit()` after
  status update. Consolidates from N+2 to 2 commits.
- **AWS:** `await aws.submit_batch_manifest_job_async(...)`.

### GET /v1/parser/jobs/{job_id} (`GetParserJob`)

- **Handler:** `async def get_parser_job`.
- **Endpoint:** `AsyncEndpoint`, `async def execute`.
- **DB:** `await self.database.find_by(ParserJob, id=job_id)` for the
  lookup. `_sync_batch_status` renamed to `_sync_batch_status_async` and
  is now `async def`; the single `.commit()` inside it becomes `await`.
- **AWS:** `await aws.describe_batch_job_async(...)` + `await
  aws.get_s3_object_async(...)`. `map_batch_status_to_parser_status` is
  a pure mapping — stays sync, called without `await`.

### POST /v1/parser/batches (`CreateParserBatch`)

- **Handler:** `async def create_parser_batch`.
- **Endpoint:** `AsyncEndpoint`, `async def execute`.
- **DB:** `await self.database.create(parser_batch)` (need the batch id
  for the parser_job FK), then per-job `self.database.db.add(...)` (no
  per-row commit), then a single `await self.database.db.commit()` +
  per-job `await self.database.db.refresh(pj)`, then one final `await
  commit()` after status update. Old code did N+2 commits; new does 3.
- **AWS:** `await aws.submit_batch_manifest_job_async(...)`.
- **Callback URL:** the `settings.api_base_url` branch is preserved
  byte-for-byte; the extra env dict + conditional still hands off to
  AWS in kwargs.

### GET /v1/parser/batches (`ListParserBatches`)

- **Handler:** `async def list_parser_batches`.
- **Endpoint:** `AsyncEndpoint`, `async def execute`.
- **DB:** two awaited `self.database.db.execute(select(...))` calls —
  one for `ParserBatch` (with `selectinload(ParserBatch.parser_jobs)`),
  one for `ImportJob` (only when `batch_ids` is non-empty). The
  dismissed-batch filter stays in Python; same semantics as sync.

### GET /v1/parser/batches/{batch_id} (`GetParserBatch`)

- **Handler:** `async def get_parser_batch`.
- **Endpoint:** `AsyncEndpoint`, `async def execute`.
- **DB:** two awaited `execute(select(...))` calls — `ParserBatch` with
  `selectinload(parser_jobs)` for the single fetch, `ImportJob` for
  the cross-table join. Serializer `_serialize_batch` is unchanged
  (pure function).

### POST /v1/parser/batches/{batch_id}/complete (`CompleteParserBatch`)

- **Handler:** `async def complete_parser_batch` — unauthenticated by
  design (the Batch container calls it; safety from AWS re-query).
- **Endpoint:** `AsyncEndpoint`. `execute` dispatches the entire sync
  workflow via `await run_in_threadpool(_run_complete_sync, batch_id)`.
- **Sync boundary (`_run_complete_sync`):** opens a fresh sync
  `Database(db=SessionLocal())`, re-queries the batch, runs
  `complete_parser_batch(database, aws, parser_batch)` (the shared
  sync helper used by `WatchParserBatchTask`), builds the `success(...)`
  envelope, closes the session in `finally`. 404 surfaces through
  `AsyncEndpoint.run`'s normal `APIException` handling.

## Sync → async boundary inventory

- **Threadpool dispatches:** `CompleteParserBatch._run_complete_sync` is
  the only endpoint in this chunk that opens a sync `Database`; every
  other endpoint runs end-to-end on the async engine.
- **Sync helpers left sync (intentional):**
  - `parser_batch_completion.complete_parser_batch` (+ `_handle_success`,
    `_handle_total_failure`, `_mark_failed`, `_create_failure_activity`) —
    shared with `WatchParserBatchTask` (celery worker, sync-only).
- **Celery dispatch:** `watch_parser_job_task.apply_async` +
  `watch_parser_batch_task.apply_async` called from async; celery
  handles its own threading, so no wrapping needed.

## Lazy-load audit

Three response builders to audit:

- `GetParserJob.Response` — flat scalars off `parser_job` only; no
  relationship access.
- `GetParserBatch._serialize_batch` — iterates `parser_batch.parser_jobs`.
  Eager-loaded via `selectinload(ParserBatch.parser_jobs)` in the query.
  No other `.` chains.
- `ListParserBatches` — same `parser_batch.parser_jobs` iteration per
  batch, same `selectinload` hydration. `ImportJob` rows are queried
  directly (no relationship traversal).

No lazy-load / MissingGreenlet risk found.

## Test inventory

- **`test_parser.py`** — 18 tests across 4 classes:
  - `TestGetUploadUrl` (1)
  - `TestSubmitParserJob` (1)
  - `TestGetParserJob` (11) — includes 7 AWS-sync scenarios, all
    pending/already-terminal, no-output-key, no-batch-id branches.
  - `TestSubmitBatchParserJob` (4) — including the 422 validation
    branch.
- **`test_parser_batches.py`** — 13 tests across 5 classes:
  - `TestCreateParserBatch` (3) — happy path (2 groups), single group,
    empty-items 400.
  - `TestGetParserBatch` (3) — nested hydration, 404, 403.
  - `TestListParserBatches` (4) — basic list, active filter (empty),
    dismissed-all filter, pre-fanout batch.
  - `TestCompleteParserBatch` (2) — happy path (delegates to sync
    helper) + 404. Both patch
    `api.v1.parser.complete_parser_batch.SessionLocal` to return a
    `MagicMock` wrapping a `MockQuery([...])` so the threadpool body
    runs against a mocked sync session.
  - `TestCreateParserBatchCallbackUrl` (1) — callback URL extra-env
    branch.

Every test name preserved from the sync predecessor; no deletions.

## Pre/post latency capture

Parser endpoints are low-volume (recipe imports are user-initiated and
rare) so the client-latencies pipeline doesn't have a statistically
meaningful p95 delta for them on a per-day window. Per the epic's rule
#9 (party-mode 2026-04-23), post-merge observability will come from
direct `client_latencies` scrapes the next time a user pushes a batch
through the OCR path. The conversion is mechanical (sync → async, no
business-logic change) and the endpoints are I/O-bound on S3 + AWS
Batch anyway, so the latency win comes from releasing the event loop
during boto3 calls — not from DB-side gains.

## Rollback

`git revert <aam-29-commit>` + `bin/prod-deploy` (~10 min). The sync
`Endpoint` base class still exists for other not-yet-converted domains,
so both halves keep building after a revert.

## Gotchas discovered during implementation

- `_sync_batch_status` renamed to `_sync_batch_status_async` rather
  than reusing the name, so future readers don't mistake an `async def`
  with that name for the sync worker-side helper in
  `parser_batch_completion.py`.
- `submit_batch_parser_job` + `create_parser_batch` switched from N
  per-row `database.create(...)` calls (each an add+commit) to a
  single batch `db.add(...)` + single `db.commit()` + per-row
  `db.refresh(...)`. Semantic equivalent, fewer round-trips, same
  behavior for the mock layer (`MockAsyncDatabase.db.refresh` still
  has `side_effect=_apply_column_defaults`, so IDs are assigned
  at refresh time as in the sync mock).
- The `CompleteParserBatch` tests needed an extra patch
  (`api.v1.parser.complete_parser_batch.SessionLocal`) on top of the
  existing patches on `AWSService` + the sync helper itself. Without
  it, the threadpool body would try to instantiate a real session and
  fail in tests (DATABASE_URL is set to a placeholder).
- `mock_async_db.set_find_by(Model, obj, id=...)` is reused from
  aam-17 / aam-10 test infra — it registers both `find_by(Model,
  id=...)` and `where(Model, id=...).first()` lookups, so
  `GetParserJob`'s `await self.database.find_by(ParserJob, id=...)`
  and the `where`-style fallback both resolve to the same mock batch
  without extra setup.

## Parallel session contamination note

`git status` in the working copy during this chunk showed 39 modified
files + 6 untracked belonging to parallel `/dev` sessions (aam-12b,
aam-18, aam-28, aam-30). Per `project_parallel_dev_loops.md`:

- Only the 11 parser files (+ the new aam-29 story + sprint-status
  flip) are staged.
- The full `npx nx run api:test` run is not green locally because of
  cross-session WIP (e.g. `NameError: name 'Endpoint' is not defined`
  in `list_import_items.py` from the aam-18 partial conversion,
  `mock_async_db is not defined` in test_coverage_gaps.py from
  aam-12b). Those failures are owned by the parallel sessions —
  remote CI on a clean `origin/main` checkout sees only our delta
  and will be the authoritative signal.
- Parser tests run in isolation (`pytest tests/test_parser.py
  tests/test_parser_batches.py`) are 31/31 green with 100% coverage,
  which is the local evidence for this chunk.
