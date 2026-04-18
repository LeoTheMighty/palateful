# sbf-3 QA Walkthrough — s3_key import path (audio/pdf/spreadsheet)

**Story:** sbf-3-s3-key-import-path-audio-pdf-spreadsheet
**Status:** done

## What shipped

- `POST /v1/recipe-books/{id}/import` accepts `{s3_key, etag,
  mime_type}` (mutually exclusive with `file_base64`) for `audio` /
  `pdf` / `spreadsheet` source types.
- Ownership check: `s3_key` must start with
  `imports/{current_user.id}/`. 403 + `cross_user_key` otherwise.
- HeadObject handshake: 409 + `object_not_ready` if S3 doesn't see
  the object yet. Client retries per the cross-epic 3-attempt /
  500ms-backoff convention.
- Replay protection: in-DB dedupe via `ImportItem.s3_key` partial
  UNIQUE index. Second `/import` for the same key → 409 +
  `duplicate_import` (whether caught by the in-endpoint query or by
  the IntegrityError fallback).
- Per-user rate limit: 30 imports / rolling hour. 429 +
  `rate_limited` over cap; applies to the entire `/import` endpoint
  (not just s3_key path) so a base64 storm can't bypass.
- Worker (`ParseSourceTask`) reads bytes from `S3_IMPORTS_BUCKET` and
  parses them with the same audio / PDF / spreadsheet extractors as
  the inline base64 path. Multi-recipe PDFs and multi-row spreadsheets
  fan out into siblings.

## Manual smoke test (when there's a real client + AWS creds)

This depends on sbf-2's presign endpoint. Smoke test is
`presign → PUT → import → wait for activity`.

### 1. Happy path — audio

```bash
# Step 1: presign
PRESIGN=$(curl -sS -X POST http://localhost:8000/v1/imports/upload-url \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"filename":"voice.m4a","mime_type":"audio/mp4","size_bytes":1048576}')
URL=$(echo "$PRESIGN" | jq -r .upload_url)
S3_KEY=$(echo "$PRESIGN" | jq -r .s3_key)

# Step 2: PUT bytes (size_bytes must match exactly)
curl -X PUT "$URL" \
  -H "Content-Type: audio/mp4" \
  -H "Content-Length: 1048576" \
  -H "x-amz-tagging: unclaimed=true" \
  --data-binary @/tmp/voice.m4a

# Step 3: claim it
curl -X POST http://localhost:8000/v1/recipe-books/$BOOK_ID/import \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"source_type\":\"audio\",\"s3_key\":\"$S3_KEY\",\"mime_type\":\"audio/mp4\",\"file_name\":\"voice.m4a\"}"
```

Expected:
- 201 from /import. `total_items=1`.
- A celery task fires (parse_source_task). Within ~10s, the activity
  feed shows "Importing from voice memo..."
- Within ~30s, `import_items.{id}.status` transitions
  `pending → extracting → matching → completed` (or `awaiting_review`
  for low-confidence items).

### 2. Cross-user-key rejection

```bash
curl -X POST http://localhost:8000/v1/recipe-books/$BOOK_ID/import \
  -H "Authorization: Bearer $JWT" \
  -d '{"source_type":"pdf","s3_key":"imports/some-other-uuid/foo.pdf","mime_type":"application/pdf"}'
```

Expected: 403, `error_code: 293` (`CROSS_USER_KEY`).

### 3. Object-not-ready

Manually delete the S3 object after presign but before /import,
*or* call /import with a fabricated key under your own prefix that
was never uploaded:

```bash
curl -X POST http://localhost:8000/v1/recipe-books/$BOOK_ID/import \
  -H "Authorization: Bearer $JWT" \
  -d "{\"source_type\":\"pdf\",\"s3_key\":\"imports/$YOUR_USER_ID/never-uploaded.pdf\",\"mime_type\":\"application/pdf\"}"
```

Expected: 409, `error_code: 292` (`OBJECT_NOT_READY`). Client should
retry up to 3× with 500ms backoff.

### 4. Replay protection

Run the same /import call twice in a row with the same `s3_key`:

```bash
# (After a successful first call) ...
curl -X POST .../import -d "{... same s3_key ...}"
```

Expected on the second call: 409, `error_code: 294`
(`DUPLICATE_IMPORT`).

### 5. Rate limit

Fire 31 successful /import calls within an hour from the same user.
The 31st returns 429:

```json
{
  "error_code": 203,
  "error_message": "Too many imports (max 30/hour). Retry in NNNs.",
  "data": {"retry_after": "<seconds>"}
}
```

### 6. Mutual exclusion

```bash
curl ... -d '{"source_type":"audio","s3_key":"imports/$ME/x.m4a","file_base64":"Zm9v","file_name":"x.m4a"}'
```

Expected: 400, `error_code: 37` (`INVALID_REQUEST`),
`error_message: "s3_key and file_base64 are mutually exclusive"`.

## What's NOT in this story (don't QA here)

- `video_file` source type / ffmpeg in worker — sbf-4.
- Social URL routing promoted to endpoint — sbf-5.
- Real AWS round-trip (presign → PUT → import → recipe). The pieces
  are all wired and unit-tested but the integration only happens in a
  staging environment with real creds.

## Automated test coverage

```
services/api/tests/test_import.py::TestStartImportS3Key            # 7 tests
services/api/tests/test_parse_source_task.py                       # 3 tests
```

All pass under `DATABASE_URL=postgresql://test/test poetry run pytest`.
`migrator:check-models` confirms no model/migration drift.
