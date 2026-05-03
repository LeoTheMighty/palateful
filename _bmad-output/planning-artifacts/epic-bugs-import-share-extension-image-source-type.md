<!-- created from /audit triage 2026-05-03 -->
# Epic: Bugs — Import: share-extension `image` source_type

## Overview

The iOS share-extension photo flow has been firing 400s on
`POST /v1/recipe-books/{id}/import` since at least 2026-04-26
(`error_code=168 IMPORT_INVALID_SOURCE_TYPE`, "Unsupported source type:
image"). The share extension uploads the image to S3 via the
SBF presigned-upload contract and POSTs `{source_type: "image",
s3_key, etag}`, but the server only knows `audio | pdf | spreadsheet |
video_file` for the s3_key path — `image` was never wired up. Every
shared image is silently dropped (the share sheet has already
dismissed by the time the import POST fires; `markFailed` only emits
telemetry).

This epic adds the missing `image` branch end-to-end so the iOS share
extension can actually deliver photos into the import-review queue.

## Goal

Backend accepts `source_type=image` on `/import` via the s3_key
contract, fetches the bytes from S3 in the worker, runs OpenAI
`gpt-4o-mini` vision extraction (the existing
`extract_recipe_from_image` path), and lands a reviewable ImportItem
in the user's import-review queue — same downstream UX as every other
source type.

## Why now / impact

- Every iOS share-sheet photo import has been failing for 7+ days.
- Currently only the test user is hitting it (low aggregate count) but
  the flow is fully broken for every shipped client; once we exit
  closed-beta this will block the most natural import path on iOS.

## End-user flow

1. User long-presses a recipe image in Photos / Safari / a cooking
   blog and taps Share → Palateful.
2. The PalatefulShare extension calls `POST /v1/imports/upload-url`
   (SBF-2), uploads the JPEG/HEIC to S3 via presigned PUT, then POSTs
   `/v1/recipe-books/{book_id}/import` with `{source_type: "image",
   s3_key, etag, mime_type, idempotency_key}`.
3. Backend creates an `ImportJob(source_type="image")` and one
   `ImportItem(source_type="image", s3_key=...)`.
4. `ParseSourceTask` no-ops (no decoding needed) and dispatches to
   `ExtractRecipeTask`.
5. `ExtractRecipeTask` reads bytes from S3, calls
   `extract_recipe_from_image` (gpt-4o-mini vision), populates
   `parsed_recipe`, transitions item to `awaiting_review`.
6. User opens the Activity Hub / Imports tab and sees the recipe ready
   to review.

## Backend changes

### `services/api/src/api/v1/import_job/start_import.py`

- Add `"image"` to `_S3_KEY_SOURCE_TYPES`.
- New `elif params.source_type == "image"` branch (mirrors `video_file`
  at lines 230–240): require `s3_key`; no `file_base64` fallback (the
  share extension only offers presigned-upload). Run
  `_validate_s3_key_inputs`. `source_filename = params.file_name or
  params.s3_key`.
- The existing s3-keyed ImportItem creation block (lines 446–480) then
  picks up `source_type="image"` automatically because it iterates
  `_S3_KEY_SOURCE_TYPES`.

### `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`

- Add `"image"` to the no-op tuple at the bottom of `execute`'s
  if/elif (`("photo", "text", "spreadsheet", "audio", "pdf",
  "video_file")` → add `"image"`).
- Do **not** add `"image"` to `_S3_KEYED_SOURCE_TYPES` — the parse
  stage is a no-op for images. Bytes are fetched in the extract stage
  instead, since vision extraction is a single round-trip (unlike
  audio/pdf which need a decode step before AI extraction).

### `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`

- New `elif item.source_type == "image":` branch in
  `_extract_single_item`. Fetch bytes via `AWSService.read_object` from
  `S3_IMPORTS_BUCKET`, call `extract_recipe_from_image`, run the
  result through `_update_item_from_result` (which already handles
  multi-recipe fanout, cost accounting, and confidence scoring).
- Why OpenAI Vision (`gpt-4o-mini`), not HunyuanOCR via AWS Batch:
  vision extractor returns a fully structured recipe in a single API
  call — no second pass needed. The HunyuanOCR/parser-batch chain is
  designed for multi-image fanout and would require a second
  text-extraction pass. For one share-sheet image the vision path is
  simpler, faster, and cheaper.

## Tests

- API: image+s3_key returns 201 and creates the right job/item shape;
  s3_key + file_base64 simultaneously returns 400 INVALID_REQUEST;
  image without s3_key returns 400 INVALID_REQUEST (not 168).
  Cross-user s3_key still returns 403.
- Worker: `_extract_single_item` fetches S3 bytes for an image item,
  calls vision extractor, and writes parsed_recipe + sets status to
  `awaiting_review`.
- (Optional) Worker test that the parse stage is a no-op for image —
  no S3 fetch, item stays `pending`, dispatch fans out to extract.

## Out of scope

- Multi-image grouped imports (one share = many photos). The share
  extension only sends one image per share today.
- Renaming "image" → "photo" or vice versa. The legacy `photo`
  source_type carries client-side OCR text; it is a different
  contract and stays as-is.

## Stories

1. **share-img-1: Add `image` source_type end-to-end (start_import +
   parse_source + extract_recipe)** — single story, see
   `share-img-1-image-source-type-end-to-end.md`.

## Status

In-progress (created from /audit triage 2026-05-03). Single-story epic.
