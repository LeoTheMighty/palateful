# Story `ifh-1` — Backend: request_id propagation + retryable classification on /import & /upload-url

**Status:** review
**Epic:** `epic-import-flow-hardening`
**Source:** `_bmad-output/planning-artifacts/epic-import-flow-hardening.md`

## Goal

Close two server-side gaps that compounded the recent silent-import-failure incident:

1. **Observability:** `import_router.py` did not pass FastAPI's `Request` to the endpoint base class. With `self.request = None`, the audit writer (`_log_api_error_to_db`) skipped the `request_id` capture branch, so every `error_logs` row from `/v1/recipe-books/.../import` had a null correlation handle. Triage had to fall back to `user_id + path` queries.
2. **Retry contract:** the wire body of every error response surfaced only `error_code` and `error_message`. The iOS Share Extension and Dart reconciler had to maintain a parallel client-side classification (4xx → permanent vs. 5xx → transient) — fragile, drifts from the server's actual semantics, and gets the OBJECT_NOT_READY 409 case wrong (it's transient, not permanent).

## What changed

### `libraries/utils/utils/api/endpoint.py`
- `APIException.__init__` accepts `retryable: bool | None = None` and stores it on the instance.
- `Endpoint.run()` and `AsyncEndpoint.run()` thread `e.retryable` into the `failure(...)` call when an `APIException` is caught.
- `failure(...)` accepts `retryable: bool | None = None`; when set, it surfaces `"retryable": <bool>` at the top level of the result dict.
- `Endpoint.handle_result(...)` lifts `retryable` from the result dict to the **top level** of the JSON response body (alongside `error_code`, not nested under `data`). When `retryable` is unset, the wire shape is unchanged — every endpoint outside the import path keeps its current contract, so rolling out per-endpoint is safe and incremental.

### `services/api/src/api/v1/import_job/start_import.py`
- Every `APIException` raise and the rate-limit `failure(...)` and the duplicate-import 409 carries an explicit `retryable=` kwarg per the classification table:
  - `400 INVALID_REQUEST` → `False`
  - `400 IMPORT_INVALID_SOURCE_TYPE` → `False`
  - `403 RECIPE_BOOK_ACCESS_DENIED` → `False`
  - `403 CROSS_USER_KEY` → `False`
  - `404 RECIPE_BOOK_NOT_FOUND` → `False`
  - `409 OBJECT_NOT_READY` → `True` (S3 visibility lag — the canonical transient)
  - `409 DUPLICATE_IMPORT` → `False` (file already exists; re-POST would loop)
  - `429 RATE_LIMITED` → `True` (`retry_after` honored as the lower-bound)
- Includes share-img-1's new `image` source-type branch (carried along from the parallel commit) — also classified as `retryable=False` for consistency.

### `services/api/src/api/v1/import_job/get_upload_url.py`
- All three `APIException` raises (`size_bytes <= 0`, `FILE_TOO_LARGE`, `UNSUPPORTED_MIME`) marked `retryable=False`.

### `services/api/src/routers/v1/import_router.py`
- Every handler accepts `request: Request` and forwards it via `request=request` to the corresponding `.call(...)` invocation. This is the structural fix for the request_id observability gap. Without it, `Endpoint._log_api_error_to_db` reads `self.request` as None and falls through to writing a row with `request_id=null` (the symptom that prompted this story).
- `from fastapi import APIRouter, Depends, Query, Request` — added `Request` import.
- All 19 handlers in the file updated; the import path now matches the `client_latency_router.py` pattern, which was the only router doing this correctly before today.

### `services/api/tests/test_import.py`
- New `TestImportFlowHardeningRetryable` (10 tests): one per failure path on `/import` + `/upload-url`, asserts the wire body includes `"retryable": <bool>` with the expected value. Covers RATE_LIMITED (transient), OBJECT_NOT_READY (transient), DUPLICATE_IMPORT/CROSS_USER_KEY/INVALID_REQUEST/RECIPE_BOOK_ACCESS_DENIED/RECIPE_BOOK_NOT_FOUND/IMPORT_INVALID_SOURCE_TYPE/FILE_TOO_LARGE/UNSUPPORTED_MIME (all permanent), plus the s3_key/file_base64 mutex.
- New `TestImportFlowHardeningRequestId` (2 tests): direct assertion that `_log_api_error_to_db` captures `request.state.request_id` when `self.request` is wired (the post-router-fix state) and writes null when it isn't (the pre-router-fix state — backstop so a regression here would surface visibly).
- New `TestFailureHelperRetryable` (4 tests): `failure(retryable=...)` surfaces the field correctly; `handle_result` lifts it to the top level; default keeps wire shape unchanged.

## Acceptance criteria status

- [x] Every endpoint in `import_router.py` accepts `request: Request` and forwards it to `.call(...)` — verified by all 2566 tests passing through the new signatures.
- [x] `failure(...)` accepts `retryable: bool | None`; included in body when set.
- [x] `StartImport.execute` passes `retryable` on every failure path per the classification table.
- [x] `GetImportUploadUrl.execute` passes `retryable=False` on its three failure paths.
- [x] Wire shape unchanged for endpoints that don't classify (the `retryable` key is omitted when `None`).
- [x] Parametrized failure-path tests cover each classification.
- [x] `_log_api_error_to_db` writes `request_id` when wired (unit test asserts).
- [x] `_log_api_error_to_db` writes `request_id=null` when `self.request` is None (regression backstop).
- [x] 100% line coverage maintained.
- [x] `npx nx run api:test` green (2566 passed).
- [x] `npx nx run api:lint` + `npx nx run utils:lint` green.

## QA walkthrough

See `ifh-1-qa-walkthrough.md` for the full reviewer-runnable checklist.

## Notes / collisions

- **share-img-1 parallel commit (c2f7982).** The share-extension image-source-type fix landed concurrently and rewrote `start_import.py` twice during this story (adding the `image` source_type). Final state of `start_import.py` includes both share-img-1's `image` branch (with `retryable=False` applied for consistency) AND every other branch's `retryable=` classification.
- **`_log_api_error_to_db` is gated on `ENVIRONMENT == "prod"`.** The router fix is real but its primary observable effect (request_id in error_logs) only fires in prod. The unit test patches the env to verify the prod path.
- **iOS Swift `parseErrorPayload`** (UploadService.swift:334–342) currently reads only `error_code` and `error_id`. Reading the new top-level `retryable` field is part of `ifh-3` — out of scope here, but flagged for the next story.
- **Platform-wide `Request` forwarding sweep is deferred.** 25 of 27 routers still don't forward `Request`. The audit-cited surface was the import path; broader sweep belongs in a separate observability epic per the epic file's "Out of scope" section.
