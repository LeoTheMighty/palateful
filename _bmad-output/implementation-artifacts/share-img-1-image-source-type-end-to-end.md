# Story share-img-1: Add `image` source_type end-to-end

**Status:** ready-for-dev

**Epic:** epic-bugs-import-share-extension-image-source-type

## Why

The iOS share-extension photo flow has been firing 400s (`error_code=168
IMPORT_INVALID_SOURCE_TYPE`) since 2026-04-26. The extension uploads the
image to S3 then POSTs `{source_type: "image", s3_key, etag, mime_type}`
but the server only knows `audio | pdf | spreadsheet | video_file` for
the s3_key path. Every shared image is silently dropped because the
share sheet has already dismissed by the time the import POST fires.

The client is correct (the SBF s3_key contract is the right shape for
files this size); the server is missing the matching `image` branch.

## Acceptance criteria

- **AC 1.** `POST /v1/recipe-books/{book_id}/import` with
  `{source_type: "image", s3_key, etag, mime_type, idempotency_key}`
  returns 201 and creates an `ImportJob(source_type="image")` plus one
  `ImportItem(source_type="image")` carrying the s3_key on the
  dedicated column. Same idempotency, rate-limit, cross-user, and
  not-yet-visible paths as the existing s3_key source types.
- **AC 2.** `ImportItem(source_type="image")` is dispatched to
  `ExtractRecipeTask` which reads the bytes from S3
  (`S3_IMPORTS_BUCKET`), calls `extract_recipe_from_image`
  (gpt-4o-mini vision), and writes `parsed_recipe`. The item ends up
  in `awaiting_review` like every other extracted item.
- **AC 3.** Bad inputs surface with `error_code=INVALID_REQUEST`, not
  the falling-through `IMPORT_INVALID_SOURCE_TYPE` (168):
  - `source_type=image` without `s3_key` → 400 INVALID_REQUEST.
  - `source_type=image` with both `s3_key` and `file_base64` → 400
    INVALID_REQUEST (the existing mutex check at line 126 already
    covers this; verify in test).
- **AC 4.** Regression tests cover the API branch and the worker
  branch; existing s3_key tests for audio/pdf/video_file continue to
  pass.

## Implementation notes

### Files

- `services/api/src/api/v1/import_job/start_import.py`
  - Add `"image"` to `_S3_KEY_SOURCE_TYPES`.
  - Add `elif params.source_type == "image":` branch around line 230,
    mirroring the `video_file` branch (s3_key required, no base64
    fallback). Call `_validate_s3_key_inputs(params, user)`.
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`
  - Add `"image"` to the no-op tuple
    `("photo", "text", "spreadsheet", "audio", "pdf", "video_file")` at
    the bottom of the if/elif chain in `execute`. The parse stage is
    intentionally a no-op for images.
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
  - Import `extract_recipe_from_image` from
    `utils.services.recipe_extractors`.
  - Add `_aws_service()` helper (mirrors the one in
    `parse_source_task.py`).
  - Add `elif item.source_type == "image":` in `_extract_single_item`
    around line 175 (just after the `photo` branch). Resolve s3_key
    from `item.s3_key` (or `raw_data.s3_key` as fallback for
    consistency with `parse_source_task` behavior). Read bytes,
    call `extract_recipe_from_image`, then `_update_item_from_result`.

### Tests

- `services/api/tests/test_import.py`:
  - `test_image_s3_key_accepted` — `source_type=image` with valid
    s3_key → 201, source_type echoed, parse_source dispatched.
  - `test_image_without_s3_key_rejected` — missing s3_key → 400 with
    `INVALID_REQUEST` (NOT `IMPORT_INVALID_SOURCE_TYPE`).
  - `test_image_s3_key_mutual_exclusion_with_base64_returns_400` —
    s3_key + file_base64 → 400 INVALID_REQUEST.
  - `test_image_cross_user_s3_key_returns_403` — cross-user prefix →
    403 CROSS_USER_KEY (regression of existing protection).
- `services/api/tests/test_parse_source_task.py`:
  - `test_image_parse_stage_is_no_op` — image source_type with s3_key
    on the item: `_parse_s3_keyed_files` is NOT called; item stays
    pending; `extract_task.delay` is fanned out.
- `services/api/tests/test_extract_recipe_task.py` (or extend whichever
  existing test file already exercises `_extract_single_item`):
  - `test_image_extract_fetches_s3_and_calls_vision` — given an image
    ImportItem with s3_key, the task calls
    `aws.read_object(s3_key, S3_IMPORTS_BUCKET)`, passes bytes to
    `extract_recipe_from_image`, and writes parsed_recipe to the item
    via `_update_item_from_result`.

### Why OpenAI Vision (gpt-4o-mini), not HunyuanOCR via AWS Batch

The `vision_extractor` already exists, returns a fully structured
`ExtractionResult` in one API call, and is the same path the legacy
`photo` source_type uses *after* client-side OCR. Routing share-extension
images through it means:

- One AI round-trip (HunyuanOCR would need OCR → text → second
  AI pass to extract structured recipe).
- No new AWS Batch wiring; no parser_batch fanout for what is always a
  single image per share.
- Same downstream path as JSON-LD / URL extraction (returns
  `ExtractionResult`, handled by `_update_item_from_result` which
  supports multi-recipe fanout if the model splits a cookbook
  facing-page).

If we ever decide to multi-image-batch the share extension (out of
scope for this story), we can revisit and route through the existing
parser_batch path.

## QA walkthrough

See `share-img-1-qa-walkthrough.md`.

## File List

(To be filled in by dev workflow)

## Dev notes

- The 80 MB RSS ceiling on the share extension (documented at
  `app/ios/PalatefulShare/UploadService.swift:21`) is the reason
  client-side OCR was rejected up front. No change needed.
- The s3_key/etag handshake, idempotency_key, and rate-limit are all
  inherited from the existing s3_key path — image rides on the same
  rails as audio/pdf/video_file.
- Client (`app/ios/PalatefulShare/ShareViewModel.swift:310` +
  `UploadService.swift:50`) is already correct; this story is
  server-only.
