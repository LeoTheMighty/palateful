# QA Walkthrough — share-img-1: image source_type end-to-end

## Pre-reqs

- Latest server deployed to staging (or run `docker compose up`
  locally with the worker container).
- iOS share extension on the latest TestFlight build (no client change
  is part of this story; just verify the existing client works
  end-to-end).

## Happy path — share an image from Photos

- [ ] Open Photos.app on iOS, pick a recipe screenshot or a photo of a
      printed recipe page.
- [ ] Tap Share → Palateful (PalatefulShare extension).
- [ ] Pick the destination recipe book; tap Save.
- [ ] Open Palateful, navigate to Imports.
- [ ] Verify within ~30s an `awaiting_review` item appears with a
      pulled-out recipe (name, ingredients, instructions).
- [ ] Open the import item, approve it; recipe is created.

## API contract — direct curl (sanity check)

- [ ] `POST /v1/imports/upload-url` with
      `{filename: "test.jpg", mime_type: "image/jpeg",
      size_bytes: 12345}` returns `{upload_url, s3_key}`.
- [ ] `PUT` the bytes to `upload_url`; capture the `ETag`.
- [ ] `POST /v1/recipe-books/{book_id}/import` with
      `{source_type: "image", s3_key, etag, mime_type: "image/jpeg",
      idempotency_key: <uuid>}` returns 201 with
      `source_type=image`.
- [ ] Re-POST the same request → returns the original job (idempotency
      hit, not a duplicate).

## Error paths

- [ ] `POST /import` with `source_type=image` and **no** s3_key →
      400 `INVALID_REQUEST` ("s3_key is required for image import").
      Must NOT be `IMPORT_INVALID_SOURCE_TYPE` (168).
- [ ] `POST /import` with `source_type=image` and **both** s3_key and
      file_base64 → 400 `INVALID_REQUEST` (mutex check fires before
      the source-type validator).
- [ ] `POST /import` with `source_type=image` and an s3_key whose
      prefix is another user's id → 403 `CROSS_USER_KEY`.
- [ ] `POST /import` with `source_type=image` and a valid-looking
      s3_key that doesn't exist in S3 (e.g., random UUID) → 409
      `OBJECT_NOT_READY`.

## Worker observability

- [ ] Tail worker logs while the happy path runs. Verify:
  - `parse_source_task` runs, logs an items_created=1 result, fans out
    to `extract_recipe_task`.
  - `extract_recipe_task` logs the gpt-4o-mini vision call (cost in
    cents on the result row).
  - No `IMPORT_INVALID_SOURCE_TYPE` errors in `error_logs` for the
    request_id.

## Regression — existing source types

- [ ] Audio share via the SBF s3_key path: still works (mp3 → Whisper
      → text item → extract_recipe_task).
- [ ] PDF s3_key path: still works (multi-recipe fanout intact).
- [ ] Photo (legacy `source_type=photo` with `ocr_texts`): still works
      from the Flutter Recipe-Card-Tap path.
- [ ] URL imports: unaffected.

## Cleanup

- [ ] Verify the import item lands in `awaiting_review`, not `failed`,
      not `extracting`.
- [ ] Verify total_ai_cost_cents on the job is non-zero (vision call
      always costs).
- [ ] Verify error_logs has no `service=api error_type=APIException
      error_code=168` entries since the test started.
