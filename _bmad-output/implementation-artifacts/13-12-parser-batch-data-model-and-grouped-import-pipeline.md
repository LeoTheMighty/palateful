# Story 13.12: Parser Batch Data Model & Grouped Import Pipeline

**Status:** complete

## Summary

Introduce a first-class `ParserBatch` entity that groups N parser jobs together with a `group_index` per job, and rework `WatchParserJobTask` so it waits for **all jobs in a batch to reach a terminal state** before fanning out to **one ImportJob per group_index**, with OCR texts from all jobs in a group concatenated into a single ImportItem. This fixes the "page 2 is missing from my recipe" bug (currently each image becomes its own recipe) and lays the foundation for the batch import UX in story 13.13.

## User Value

Today, selecting multiple images for a single recipe silently creates N fragmented recipes — there's no way to say "these three photos are the same recipe's pages 1–3" and no way to say "these five photos are actually two different recipes." This story introduces the data model that makes both of those things possible. Users won't see a visible UI change from this story alone; it unblocks 13.13.

## The Bug This Fixes

`libraries/utils/utils/tasks/import_tasks/watch_parser_job_task.py:125-189` — `_handle_success` runs **per parser job** and each invocation creates its own `ImportJob(total_items=1)` + `ImportItem`. There is no concept of "wait until the sibling parser jobs also finish, then combine." Combined with the fact that `services/api/src/api/v1/parser/submit_batch_parser_job.py` doesn't set `recipe_book_id` on the parser jobs it creates (so the server-side auto-import path is entirely skipped for batch submissions), the multi-image flow relies on the frontend's fallback `_startImportPipeline` path — which is fragile and dies if the user closes the app.

## Scope

**In scope:** photo import path (camera / gallery multi-select). All other import paths (URL bulk, PDF, spreadsheet, text, audio) continue to use their existing flows untouched. The `ParserBatch` primitive is built generically so other paths can opt in later, but no other paths are migrated in this story.

## Acceptance Criteria

### Data Model

1. New table `parser_batches` with columns:
   - `id` (UUID, PK)
   - `user_id` (UUID, FK → users.id, CASCADE, indexed)
   - `recipe_book_id` (UUID, FK → recipe_books.id, SET NULL, nullable)
   - `status` (String, one of: `pending | submitted | running | partial | succeeded | failed`, indexed)
   - `group_count` (Int, number of distinct `group_index` values in this batch)
   - `error_message` (Text, nullable)
   - `created_at`, `updated_at`, `completed_at` (timestamps)
2. `parser_jobs` gains two new columns:
   - `parser_batch_id` (UUID, FK → parser_batches.id, CASCADE, nullable, indexed) — nullable so existing single-image flow keeps working
   - `group_index` (Int, default 0) — images sharing a `group_index` within the same batch become one recipe
3. Alembic migration created in `services/migrator/migrations/versions/` following the existing `YYYYMMDDHHMMSS_...py` naming convention
4. `ParserBatch` SQLAlchemy model in `libraries/utils/utils/models/parser_batch.py` with relationships to `User`, `RecipeBook`, and `ParserJob` (one-to-many)
5. `ParserJob.parser_batch` relationship added for back-navigation

### API — New Endpoints

6. `POST /v1/parser/batches` — creates a batch + N parser jobs in one call
   - Request body: `{ recipe_book_id: UUID, items: [{ s3_key: str, group_index: int }] }`
   - Submits a **single** AWS Batch job for all items (reusing the existing manifest submission path from `submit_batch_parser_job.py`)
   - Sets `batch_job_id` + `status=submitted` on all parser jobs
   - Dispatches a single `watch_parser_batch_task(batch_id)` Celery task
   - Returns `{ id, status, jobs: [{ id, input_s3_key, group_index }] }`
7. `GET /v1/parser/batches/{id}` — returns batch status + nested job details
   - Response includes: `id, status, group_count, recipe_book_id, created_at, completed_at, error_message, jobs: [{ id, status, input_s3_key, group_index, extracted_text, error_message }], import_jobs: [{ id, status }]`
8. `GET /v1/parser/batches?active=true&limit=20` — lists user's batches, defaulting to non-terminal statuses when `active=true`
9. Existing endpoints (`POST /v1/parser/jobs`, `POST /v1/parser/batch-jobs`) remain functional for backward compatibility — they simply don't use the new batch abstraction

### Pipeline Rework — `WatchParserJobTask` → `WatchParserBatchTask`

10. New task `WatchParserBatchTask` in `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py`:
    - Polls AWS Batch (same 30s interval, same 20-minute timeout) until the single shared `batch_job_id` reaches a terminal state
    - On success: reads S3 output for **every** parser job in the batch in parallel, populates `extracted_text` on each, sets `parser_job.status = succeeded`
    - Groups parser jobs by `group_index` and for **each group** creates exactly one `ImportJob` + one `ImportItem` where `raw_data = { text: concat(ocr_texts), s3_keys: [...] }`. Texts within a group are joined with a clear page separator (e.g., `\n\n--- page break ---\n\n`)
    - Threads the per-group `s3_keys` through `raw_data` so downstream `extract_recipe_task` / `create_recipe_task` can pick an `image_url` from the actual source images
    - Links each `ImportJob` back to its parent `ParserBatch` via a new nullable `parser_batch_id` column on `import_jobs` (migration)
    - Dispatches `parse_source_task` per created `ImportJob`
    - Sets `parser_batch.status` to `succeeded` if all groups produced import jobs, `partial` if some OCR jobs failed but others succeeded, `failed` if all failed
    - On failure: sets `parser_batch.status = failed`, creates one `parser_job_failed` activity with the batch's user-visible error
11. Old `WatchParserJobTask` is retained for the existing single-image path; new code path uses `WatchParserBatchTask` exclusively
12. Duplicate-guard: if `parser_batch.status` is already terminal, the task is a no-op (matches the existing pattern in `watch_parser_job_task.py:60-66`)

### Tests

13. `services/api/tests/test_parser_batches.py` — new test file covering:
    - Creating a batch with 3 jobs split into 2 groups (2+1) returns the expected response shape
    - `GET /v1/parser/batches/{id}` reflects correct nested state
    - `GET /v1/parser/batches?active=true` filters out terminal batches
    - Auth: users cannot see other users' batches
14. `libraries/utils/utils/tasks/import_tasks/tests/test_watch_parser_batch_task.py` (or sibling in the matching test directory) — new test file covering:
    - Happy path: 3 jobs, 1 group → 1 ImportJob with concatenated OCR text
    - Happy path: 3 jobs, 2 groups → 2 ImportJobs, each with its own OCR text
    - Partial failure: 2 jobs succeed, 1 fails → `parser_batch.status = partial`, import jobs created for the successful group only
    - Total failure: all jobs fail → `parser_batch.status = failed`, no import jobs created, failure activity emitted
    - Idempotency: running the task twice on a terminal batch is a no-op

## Technical Approach

### Migration

Create `services/migrator/migrations/versions/{YYYYMMDDHHMMSS}_add_parser_batches.py` following the pattern in `20260410000000_add_recipe_book_id_to_parser_jobs.py`:

```python
# Upgrade
op.create_table(
    "parser_batches",
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("recipe_book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recipe_books.id", ondelete="SET NULL"), nullable=True),
    sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
    sa.Column("group_count", sa.Integer, nullable=False, server_default="1"),
    sa.Column("error_message", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
)

op.add_column("parser_jobs", sa.Column("parser_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parser_batches.id", ondelete="CASCADE"), nullable=True))
op.create_index("ix_parser_jobs_parser_batch_id", "parser_jobs", ["parser_batch_id"])
op.add_column("parser_jobs", sa.Column("group_index", sa.Integer, nullable=False, server_default="0"))

op.add_column("import_jobs", sa.Column("parser_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parser_batches.id", ondelete="SET NULL"), nullable=True))
```

### Endpoint Structure

Follow the existing `services/api/src/api/v1/parser/` pattern — one file per endpoint (`create_parser_batch.py`, `get_parser_batch.py`, `list_parser_batches.py`) registered in `parser_router.py`.

### Task File

Follow the existing pattern in `libraries/utils/utils/tasks/import_tasks/watch_parser_job_task.py` — `BaseTask` subclass, registered at bottom of file via `celery_app.register_task(...)`.

## Files Affected

**New:**
- `libraries/utils/utils/models/parser_batch.py`
- `libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py`
- `services/api/src/api/v1/parser/create_parser_batch.py`
- `services/api/src/api/v1/parser/get_parser_batch.py`
- `services/api/src/api/v1/parser/list_parser_batches.py`
- `services/migrator/migrations/versions/{new}_add_parser_batches.py`
- `services/api/tests/test_parser_batches.py`
- Matching test file for `watch_parser_batch_task`

**Modified:**
- `libraries/utils/utils/models/parser_job.py` — add `parser_batch_id`, `group_index`, relationship
- `libraries/utils/utils/models/import_job.py` — add `parser_batch_id` nullable FK
- `libraries/utils/utils/tasks/import_tasks/__init__.py` — register new task
- `services/api/src/api/v1/parser/__init__.py` — export new endpoints
- `services/api/src/routers/v1/parser_router.py` — wire new routes

## Out of Scope

- Frontend changes (owned by story 13.13)
- Migrating URL bulk import / PDF / spreadsheet / text / audio paths to use `ParserBatch`
- Live progress streaming / WebSockets — polling via the new endpoints is sufficient for 13.14
- Retrying individual failed parser jobs within a batch — a failed job taints its group

## Dependencies

- None — all needed upstream (`ImportJob`, `ImportItem`, `parse_source_task`, AWS Batch submission) already exists
