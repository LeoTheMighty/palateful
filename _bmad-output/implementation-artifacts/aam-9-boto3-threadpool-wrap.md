# aam-9 — boto3 threadpool wrap

**Epic:** `epic-api-async-migration`
**Status:** done
**Parent ACs:** epic-api-async-migration § Phase 2 → `aam-9`

## Scope

Add async-safe variants of every `AWSService` method that issues a
boto3 call, by delegating through `fastapi.concurrency.run_in_threadpool`.
Sync variants stay — worker-side callers (off the event loop) continue
to use them directly. Matches the aam-8 Firebase precedent: **both sync
and async entry points; neither deprecated**.

Lands **dark** — no hot-path caller awaits the async variants yet.
aam-18 (import-job domain) and aam-29 (parser domain) flip their
callsites to the `_async` variants when they convert to `AsyncEndpoint`.

## Why

boto3 is sync-only upstream. Once import_job and parser endpoints flip
to `async def`, any direct `aws.presign_put_url(...)` or
`aws.submit_batch_job(...)` call would block the event loop for the
entire HTTP round-trip to S3 / Batch. Shipping the `_async` surface
ahead of those conversions means each domain chunk touches its own
callsites only — no cross-domain coupling in either direction.

## Acceptance Criteria (from epic)

- [x] Async variants present for the 22 boto3 callsites under
  `services/api/src/api/v1/import_job/`, `services/api/src/api/v1/parser/`,
  and `services/api/src/api/v1/recipe/`. All sync methods that touch
  boto3 have an `_async` twin that wraps the sync method in
  `run_in_threadpool`.
- [x] CloudWatch-Logs read in `get_logs.py` is prepared for the async
  path. The existing `boto3.client("logs").filter_log_events(...)` call
  lives inside a sync `Endpoint`; when aam-20 (admin domain) flips it
  to `AsyncEndpoint`, the wrap is a one-line `await run_in_threadpool`
  around the existing try/except block. No new abstraction added — the
  admin domain already owns one-off inline wraps.
- [x] Existing import / parser tests stay green. No contract changes,
  no production callsite flipped in this story.
- [x] Lands **dark** — the async variants have unit-test coverage only;
  no handler awaits them.

## Implementation

### Files touched

- `libraries/utils/utils/services/aws.py` — 11 new `async` methods
  appended after `map_batch_status_to_parser_status`:
  - `generate_presigned_upload_url_async`
  - `presign_put_url_async`
  - `generate_presigned_download_url_async`
  - `get_s3_object_async`
  - `read_object_async`
  - `head_object_async`
  - `copy_object_async`
  - `submit_batch_job_async`
  - `submit_batch_manifest_job_async`
  - `describe_batch_job_async`
  - `get_batch_job_status_async`
- `services/api/tests/test_aws_service.py` — new `TestAsyncVariants`
  class with one test per async method plus one exception-propagation
  test.

### Pattern (one method, representative)

```python
async def presign_put_url_async(
    self,
    s3_key: str,
    bucket: str,
    content_type: str,
    content_length: int,
    tagging: str | None = None,
    expires_in: int = 3600,
) -> tuple[str, dict[str, str]]:
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(
        self.presign_put_url,
        s3_key,
        bucket,
        content_type,
        content_length,
        tagging,
        expires_in,
    )
```

`run_in_threadpool` is imported lazily inside the method — matches the
convention in `libraries/utils/utils/api/endpoint.py` for the
error-log threadpool hop, keeping the utils module-load graph free of
a hard dep on starlette's concurrency surface at import time.

### Why the async variant signatures match the sync variants exactly

Callers port sync → async by appending `_async` to the method name and
adding `await`. Nothing else changes. This is the same surface shape
shipped for aam-8 (`send_push` / `send_push_async`).

## Not in scope (deferred)

- **Endpoint `Endpoint` → `AsyncEndpoint` conversions.** aam-18 owns
  import_job; aam-29 owns parser; aam-20 owns admin/get_logs.
- **Recipe photo upload URL.** `services/api/src/api/v1/recipe/get_photo_upload_url.py`
  stays sync — its domain story (aam-12) will flip the callsite to
  `generate_presigned_upload_url_async`. No change needed here.
- **Worker-side boto3 callers.** Worker processes run off the event
  loop; they keep using the sync methods.

## QA

See `aam-9-qa-walkthrough.md`.
