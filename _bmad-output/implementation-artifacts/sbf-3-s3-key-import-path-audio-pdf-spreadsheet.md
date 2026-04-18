# Story sbf-3: s3_key import path for audio / pdf / spreadsheet

**Status:** done
**Epic:** epic-share-backend-foundations

## Goal

Land the consume side of the presigned-upload contract from sbf-2.
`POST /v1/recipe-books/{id}/import` learns to accept
`{s3_key, etag}` (mutually exclusive with `file_base64`), enforces
ownership via the key prefix, handshakes the upload via S3 HeadObject,
guards against replay via a new DB UNIQUE column, and rate-limits
per-user. The worker (`ParseSourceTask`) learns to fetch from the new
imports bucket and parse audio / pdf / spreadsheet bytes from S3 so
the API request doesn't have to.

This unblocks Epic Share Receiving UX and the iOS Share Extension
(both will call `presign → PUT → import` for files >2 MB).

## Scope (from epic)

- `POST /recipe-books/{id}/import` accepts `{s3_key, etag}`. Mutually
  exclusive with `file_base64`. The base64 path stays untouched
  (frozen to current callers per locked decision #1).
- Ownership: `s3_key` must start with `imports/{current_user.id}/`.
  Mismatch → `403 {error_code: "cross_user_key"}`.
- Replay: new `ImportItem.s3_key` nullable column + partial UNIQUE
  index (`WHERE s3_key IS NOT NULL`). Second `/import` with the same
  key → `409 {error_code: "duplicate_import"}`. Migration lives in
  `services/migrator/migrations/versions/`.
- Handshake: endpoint runs `HeadObject(s3_key)`. Missing object →
  `409 {error_code: "object_not_ready"}` so the client retries per
  the cross-epic 3-attempt / 500 ms-backoff convention.
- `raw_data` persists `{s3_key, original_filename, mime_type, etag}`;
  `s3_key` is duplicated into the dedicated column for the unique
  constraint.
- `ParseSourceTask` reads from S3 when `s3_key` present (for
  audio/pdf/spreadsheet source types). Base64 path still works.
- Per-user rate limit: 30 imports/hour at the endpoint, in-memory
  sliding window scoped by `user.id`. `429 {error_code:
  "rate_limited"}` on cap hit. Acceptable for the current 2-instance
  ECS deployment per the epic revision note.

**Explicitly not in this story** (sbf-4 / sbf-5):

- `video_file` source type / ffmpeg in worker — sbf-4.
- Social URL routing promoted to endpoint — sbf-5.

## Acceptance Criteria

1. `ImportItem` gains a nullable `s3_key: str | None` column. New
   migration `20260418060000_add_import_item_s3_key.py` chains off
   `irrd1fields0` (current head). Migration adds a partial UNIQUE
   index `ix_import_items_s3_key_unique` on `s3_key WHERE s3_key IS
   NOT NULL`. `downgrade()` drops the index then the column.
2. `AWSService` gains `head_object(s3_key, bucket) -> dict` (returns
   the boto3 head_object response, raises `botocore.exceptions.ClientError`
   on 404), and `read_object(s3_key, bucket) -> bytes` (raw bytes; do
   not JSON-decode like the existing `get_s3_object`).
3. `libraries/utils/utils/constants.py` exposes `S3_IMPORTS_BUCKET`
   (mirrors `PARSER_INPUTS_BUCKET`).
4. `StartImport.Params` accepts `s3_key: str | None` and `etag: str |
   None` for audio / pdf / spreadsheet source types. Mutually
   exclusive with `file_base64`. Both passed → `400 {error_code:
   "invalid_request"}`. Neither + new file source_type → `400
   {error_code: "invalid_request"}` (existing behavior preserved for
   base64 path).
5. Endpoint validates ownership: `s3_key` must start with
   `imports/{current_user.id}/`. Mismatch → `403 {error_code:
   "cross_user_key"}`.
6. Endpoint runs `head_object(s3_key, S3_IMPORTS_BUCKET)`. On 404 /
   NoSuchKey: `409 {error_code: "object_not_ready"}`. Other AWS
   errors propagate as 500.
7. Endpoint dedupes by querying `ImportItem.s3_key` first; collision
   → `409 {error_code: "duplicate_import"}`. The DB UNIQUE constraint
   is the second line of defense; on `IntegrityError` from concurrent
   inserts, return the same 409. Endpoint creates exactly one
   ImportItem with `source_type` = the input source_type (e.g.
   "audio"), `raw_data = {s3_key, original_filename, mime_type, etag}`
   and `s3_key` set on the dedicated column.
8. Per-user rate limit: 30 imports per rolling 60 minutes per
   `user.id`. Over-cap → `429 {error_code: "rate_limited"}`. Counts
   *all* `/import` calls (s3_key path AND base64 path), not just
   s3_key calls, so the cap applies uniformly. Test-only reset hook
   is exposed (mirrors `_reset_rate_limit_for_test()` in
   `send_test_push.py`).
9. `ParseSourceTask` learns a new branch: when the job has source_type
   in `{"audio", "pdf", "spreadsheet"}` and at least one item has
   `raw_data["s3_key"]` set, fetch bytes from S3 with `read_object`
   and parse using the same extractors the inline base64 path uses
   today (`transcribe_audio`, `classify_pdf` +
   `detect_recipe_boundaries` + `extract_text_from_pdf`,
   `parse_spreadsheet`). After parsing, the item's `raw_data` becomes
   `{"text": ..., "s3_key": <kept for audit>, ...}` and the
   `source_type` becomes `"text"` so the existing
   `_dispatch_extraction_tasks → ExtractRecipeTask._extract_from_raw_data`
   path takes over. PDF / spreadsheet that produce multiple recipes /
   rows fan out into siblings (mirrors the existing inline behavior).
10. Tests:
    - Endpoint: happy path for audio s3_key (HeadObject ok →
      ImportItem created → task dispatched).
    - Endpoint: cross-user-key returns 403 + `cross_user_key`.
    - Endpoint: missing S3 object returns 409 + `object_not_ready`.
    - Endpoint: replay returns 409 + `duplicate_import` (DB column
      check + IntegrityError fallback).
    - Endpoint: both `s3_key` and `file_base64` in same request → 400
      + `invalid_request`.
    - Endpoint: rate limit returns 429 + `rate_limited` after 30 calls.
    - Endpoint: rate limit reset hook works.
    - parse_source_task: s3_key audio path → reads bytes, transcribes,
      rewrites item raw_data.
    - parse_source_task: s3_key PDF (multi-recipe) → fans out siblings.
11. `npx nx run api:lint` + `npx nx run utils:lint` + `npx nx run
    api:test` + `npx nx run migrator:check-models` all pass.

## Tasks / Subtasks

- [ ] T1 — Add `s3_key` column to `libraries/utils/utils/models/import_item.py`
      (AC 1).
- [ ] T2 — Create migration `services/migrator/migrations/versions/20260418060000_add_import_item_s3_key.py`
      (AC 1).
  - [ ] T2.1 — Chain off `irrd1fields0` (current head from
        `20260418050000_add_last_retry_at_and_awaiting_review_reason.py`).
  - [ ] T2.2 — `op.add_column` + `op.create_index` partial UNIQUE.
- [ ] T3 — Add `S3_IMPORTS_BUCKET` constant to
      `libraries/utils/utils/constants.py` (AC 3).
- [ ] T4 — Extend `libraries/utils/utils/services/aws.py` (AC 2).
  - [ ] T4.1 — `head_object(s3_key, bucket) -> dict`.
  - [ ] T4.2 — `read_object(s3_key, bucket) -> bytes` (raw bytes,
        NOT JSON-decoded — distinct from existing `get_s3_object`).
- [ ] T5 — Modify `services/api/src/api/v1/import_job/start_import.py`
      (AC 4–8).
  - [ ] T5.1 — Add `s3_key` + `etag` to `Params`.
  - [ ] T5.2 — Mutual-exclusion + presence validation up front.
  - [ ] T5.3 — Cross-user-key prefix check.
  - [ ] T5.4 — `head_object` handshake + 409.
  - [ ] T5.5 — DB collision check + IntegrityError fallback.
  - [ ] T5.6 — Rate-limit guard (sliding window dict scoped by user).
  - [ ] T5.7 — ImportItem creation with the new column populated;
        `source_type` matches input.
- [ ] T6 — Modify
      `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`
      (AC 9).
  - [ ] T6.1 — New `_parse_s3_keyed_files(job)` branch.
  - [ ] T6.2 — Audio path: `read_object` → `transcribe_audio` → rewrite item.
  - [ ] T6.3 — PDF path: `read_object` → `classify_pdf` →
        `detect_recipe_boundaries` (text) or single text item
        (scanned). Fanout for multi-recipe.
  - [ ] T6.4 — Spreadsheet path: `read_object` → `parse_spreadsheet` →
        fanout per row.
- [ ] T7 — Tests in `services/api/tests/test_import.py` (AC 10).
- [ ] T8 — Tests for `parse_source_task` s3_key path
      (`services/api/tests/` if a parse_source_task test file exists,
      else add inline tests via mocking).
- [ ] T9 — `MockImportItem` default for `s3_key` field added to
      `services/api/tests/conftest.py`.
- [ ] T10 — Run lint + tests + check-models; confirm green.

## Dev Notes

- **Migration revision-id chain.** The current head on disk +
  committed-to-git is `irrd1fields0`. My migration's `down_revision`
  must be `irrd1fields0`. There is unrelated WIP in the working tree
  (model edits for `awaiting_review_reason` + `last_retry_at` not yet
  committed even though the migration file is committed) — this means
  `migrator:check-models` may report drift on those columns
  *independent of my changes*. Document but don't try to fix in this
  story.
- **Why a separate `read_object` instead of extending `get_s3_object`.**
  The existing helper does `json.loads(...)` on the body — useful for
  reading parser manifests, useless for PDF / audio bytes. A new
  bytes-returning helper is cleaner than a `decode: bool=True` toggle.
- **Why `head_object` returns a dict, not a bool.** The HeadObject
  response carries `ContentLength`, `ETag`, `LastModified` — useful
  for telemetry and for sbf-4 to verify file size before kicking off
  ffmpeg. Future-proof the helper now.
- **Mutual exclusion of `file_base64` and `s3_key`** is enforced at
  endpoint entry. We do NOT silently prefer one over the other —
  ambiguity → 400.
- **Cross-user prefix check.** The check is a literal prefix string
  match: `s3_key.startswith(f"imports/{user.id}/")`. We don't try to
  parse / normalize the key — anything matching that prefix is owned;
  anything else is a third-party key (or a typo). 403 + clear
  `error_code` so the client logs make this easy to diagnose.
- **Rate-limit window is 30 / 3600 s rolling.** In-memory dict, single
  global module-level map. The current ECS API runs 2 instances; worst
  case a single user hits 60/hr (30 per instance). Acceptable per the
  epic revision note. When Redis lands, the limiter switches to a
  shared window; until then this is the precedent (`send_test_push.py:30`).
- **Rate limit applies to the WHOLE `/import` endpoint, not just the
  `s3_key` branch.** Otherwise a base64 storm on the legacy endpoint
  bypasses the cap. Cheap correctness win.
- **Migration isolation.** The migration only adds `s3_key` (column +
  partial unique index). Don't try to backfill — there are no
  existing rows that need a value, and the column is nullable.
- **HeadObject failure modes.** boto3 raises
  `botocore.exceptions.ClientError` with `e.response["Error"]["Code"]`
  in `("404", "NoSuchKey", "NotFound")` for missing-object cases. We
  treat any of those as `object_not_ready`. Other ClientErrors (403,
  500) propagate as 500 with the exception's message.

### Source tree

- `libraries/utils/utils/models/import_item.py` — MODIFY (add column).
- `services/migrator/migrations/versions/20260418060000_add_import_item_s3_key.py` — NEW.
- `libraries/utils/utils/constants.py` — MODIFY (new constant).
- `libraries/utils/utils/services/aws.py` — MODIFY (head_object + read_object).
- `services/api/src/api/v1/import_job/start_import.py` — MODIFY
  (s3_key/etag fields, validation, rate limiter, item creation).
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py` —
  MODIFY (s3_key parsing branch).
- `services/api/tests/test_import.py` — MODIFY (add test classes).
- `services/api/tests/conftest.py` — MODIFY (MockImportItem default).

### Testing standards

- Mock `AWSService` at the appropriate import boundary (e.g.
  `api.v1.import_job.start_import._get_aws_service` if we add a
  singleton, or patch `AWSService` directly).
- For the parse_source_task tests, mock `read_object` +
  `transcribe_audio` / `classify_pdf` / `extract_text_from_pdf` / etc.
  so we don't actually decode binaries.
- Replay test must drop the rate-limit state between invocations or
  use a separate user.
- All tests run via `DATABASE_URL=postgresql://test/test poetry run
  pytest` from `services/api/`.

### Project structure notes

- `start_import.py` is already long; the s3_key path adds another
  branch. Resist the urge to refactor the whole file — that's a
  separate cleanup.
- The new constants helper can be top-of-file if `S3_IMPORTS_BUCKET`
  is already absent. (Verified — only `PARSER_INPUTS_BUCKET` exists.)

### References

- Epic: `_bmad-output/planning-artifacts/epic-share-backend-foundations.md`
  (sbf-3 ACs).
- sbf-2 story: `_bmad-output/implementation-artifacts/sbf-2-presigned-upload-url-endpoint.md`
  — provides the matching presign / s3_key shape.
- Rate-limit precedent: `services/api/src/api/v1/admin/send_test_push.py:30-54`.
- Existing migration that bumps `import_items`:
  `services/migrator/migrations/versions/20260418050000_add_last_retry_at_and_awaiting_review_reason.py`
  (chain off `irrd1fields0`).
- `_create_fanout_siblings` in
  `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py:246`
  — pattern for cleanly fanning out siblings on the same job.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Claude Opus 4.7 1M context)

### Debug Log References

- `DATABASE_URL=postgresql://test/test poetry run pytest` from
  `services/api/` → 1726 passed (was 1705 after sbf-2; +21 sbf-3
  tests, of which 7 cover the endpoint + 3 cover the parse_source_task
  s3_key branch + 1 covers the rate limiter unit + the rest cover the
  WIP irrd-2 telemetry endpoint already present in the tree).
- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test
  poetry run alembic check` (from `services/migrator/`) → "No new
  upgrade operations detected" after declaring the partial UNIQUE
  index in `ImportItem.__table_args__` (alembic was reporting "remove
  index" because the model didn't acknowledge the new constraint).
- `npx nx run api:lint` → All checks passed.
- `npx nx run utils:lint` → All checks passed (one ruff `SIM105`
  fix: replaced the temp-file unlink try/except with
  `contextlib.suppress(OSError)`).
- `npx nx run migrator:lint` → All checks passed.

### Completion Notes List

- **Two independent migration heads collided.** When I started, an
  uncommitted parallel agent had already added
  `20260418060000_add_error_logs_import_item_telemetry.py` (revision
  `irrd2tlm0001`, also chained off `irrd1fields0`). My migration was
  initially also numbered `20260418060000` and chained off
  `irrd1fields0`. Resolved by renaming my file to
  `20260418070000_add_import_item_s3_key.py` and chaining its
  `down_revision` to `irrd2tlm0001`. Now there is exactly one head:
  `sbf3s3keycol0`.
- **Index declaration on the model is required for alembic check.**
  The first run flagged "remove index ix_import_items_s3_key_unique"
  because the migration created it but the model didn't declare it.
  Adding the matching `Index(...)` to `ImportItem.__table_args__`
  silenced the drift report.
- **Rate limiter applies to the whole endpoint, not just the s3_key
  branch.** This was an explicit choice from the epic note: "applies
  to BOTH the s3_key and file_base64 paths so a base64 storm can't
  bypass the cap."
- **`_validate_s3_key_inputs` does NOT check the full epic-specified
  s3_key regex** — only the prefix. The full regex is enforced
  upstream by the presign endpoint (sbf-2 mints keys in that exact
  shape). Anything that survives the prefix check + S3 HeadObject is
  by definition a real, owned object — there's no security win from
  rejecting weird shapes after that.
- **`_parse_s3_keyed_files` extends `parse_source_task`'s source-type
  enum to include `audio` and `pdf` in the no-op fall-through branch
  (it was previously `("photo", "text", "spreadsheet")`).** The
  legacy base64 inline path needed those listed too — without that,
  any audio/pdf job (s3_key or base64) would fail at the worker with
  "Unsupported source type". Pre-existing latent bug, surfaced by
  this story; fix is one-line.
- **Error codes 292/293/294 (OBJECT_NOT_READY/CROSS_USER_KEY/
  DUPLICATE_IMPORT) were reserved by sbf-2 in advance** — no enum
  bump needed in this story.
- **PDF / spreadsheet fanout from S3 path is item-rewriting (first
  recipe/row → original item) + sibling creation (subsequent →
  new ImportItems).** Mirrors the existing inline base64 PDF
  behavior (`start_import.py:357` creates one item per recipe) but
  shifts the work to the worker.
- **No PUT-then-/import end-to-end test runs against real S3** — the
  E2E assertion in the AC is satisfied by chained mocks: presign
  endpoint test (sbf-2) + this story's HeadObject + worker
  read_object happy paths. Real S3 round-trip is a manual /
  staging-environment gate.

### File List

- MODIFIED `libraries/utils/utils/models/import_item.py` — added
  `s3_key` column + `Index(...)` declaration in `__table_args__`.
- NEW `services/migrator/migrations/versions/20260418070000_add_import_item_s3_key.py`
  — adds column + partial UNIQUE index. Chains off `irrd2tlm0001`.
- MODIFIED `libraries/utils/utils/constants.py` — added
  `S3_IMPORTS_BUCKET` env-var constant (mirrors `PARSER_INPUTS_BUCKET`).
- MODIFIED `libraries/utils/utils/services/aws.py` — added
  `head_object(s3_key, bucket) -> dict` and `read_object(s3_key,
  bucket) -> bytes`.
- MODIFIED `services/api/src/api/v1/import_job/start_import.py` —
  added `s3_key`/`etag`/`mime_type` to Params; mutual-exclusion
  guard; per-user 30/hr rate limiter (sliding window in-memory) with
  `_reset_rate_limit_for_test` hook; `_validate_s3_key_inputs`
  (prefix + HeadObject + dedupe); s3_key item-creation branch with
  IntegrityError fallback.
- MODIFIED `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`
  — added `_has_s3_keyed_items` + `_parse_s3_keyed_files` +
  `_parse_audio_bytes` + `_parse_pdf_bytes` + `_parse_spreadsheet_bytes`;
  extended the no-op fall-through enum to cover legacy audio/pdf.
- MODIFIED `services/api/tests/conftest.py` — `MockImportItem`
  defaults for `s3_key=None`, `raw_data={}`.
- MODIFIED `services/api/tests/test_import.py` — added
  `TestStartImportS3Key` (7 tests).
- NEW `services/api/tests/test_parse_source_task.py` — added
  `TestParseS3KeyedAudio` + `TestParseS3KeyedPdf` (3 tests).
