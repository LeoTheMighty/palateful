# aam-9 — QA Walkthrough

**Story:** `aam-9-boto3-threadpool-wrap`
**Date:** 2026-04-24

## Summary

Shipped async-safe twins for every sync boto3 method on `AWSService`.
Lands dark — no hot-path awaiter yet. Unblocks aam-18 (import_job
domain async) and aam-29 (parser domain async) to convert their
endpoints without touching the AWS surface area themselves.

## What changed

| File | Change |
|---|---|
| `libraries/utils/utils/services/aws.py` | +11 `async` methods mirroring every sync boto3-calling method |
| `services/api/tests/test_aws_service.py` | +12 tests (`TestAsyncVariants`) covering each async variant and exception propagation |

## Manual verification checklist

- [x] **Sync callers unchanged.** Grep confirms nothing in
      `services/api/src/` imports the `_async` suffix — every existing
      boto3 callsite still uses the sync method.
      ```
      rg 'aws\\.(generate_presigned|presign_put_url|get_s3_object|read_object|head_object|copy_object|submit_batch_job|submit_batch_manifest_job|describe_batch_job|get_batch_job_status)_async' services/api/src/
      # (empty — dark rollout)
      ```
- [x] **Sync methods preserved intact.** Each pre-existing public
      method retains its original signature and body; the async
      variants delegate back to them.
- [x] **Async variants test-covered.** `poetry run pytest
      services/api/tests/test_aws_service.py` runs 19 tests (7
      pre-existing `TestPresignPutUrl` + 12 new `TestAsyncVariants`)
      green in the local env.
- [x] **Full api suite green.** `npx nx run api:test` — **2477 tests
      pass; 100.0% coverage** (gate enforced).
- [x] **Lint clean for touched files.** `npx nx run api:lint` passes.
      `poetry run ruff check libraries/utils/utils/services/aws.py`
      passes. (The repo-wide `utils:lint` target currently fails on an
      unrelated untracked WIP file from the parallel F1 /dev loop —
      those findings belong to that story, not this one; CI on a
      clean checkout will not see them.)

## Production safety notes

- **No contract change.** Response shapes, HTTP statuses, error
  surfaces, and callsites are byte-identical to pre-aam-9. A full
  revert is `git revert` on the single commit.
- **No migration.** Zero DB changes; no Terraform; no new pip dep (the
  `fastapi.concurrency` import is already satisfied in `services/api`
  and transitively in `libraries/utils` via the existing
  `utils/api/endpoint.py` usage).
- **No env var.** Same creds, same region, same buckets.

## Observability

- No new log lines, no new metrics, no new error types. The async
  variants are pass-throughs; any exception raised inside boto3
  surfaces at the `await` site exactly as it would from the sync
  call (verified by `test_async_variant_propagates_sync_exception`).

## Unblocks

- `aam-18-import-job-domain-async` — can now port `StartImport` and
  `GetImportUploadUrl` to `AsyncEndpoint` without re-designing the
  AWS surface.
- `aam-29-parser-domain-async` — same, for `submit_parser_job`,
  `submit_batch_parser_job`, `create_parser_batch`, `get_parser_job`,
  and parser `get_upload_url`.
- `aam-20-admin-domain-async` — when it converts `get_logs.py`, the
  one-liner wraps `filter_log_events` in `run_in_threadpool` inline
  (no shared helper needed — the callsite is unique).
