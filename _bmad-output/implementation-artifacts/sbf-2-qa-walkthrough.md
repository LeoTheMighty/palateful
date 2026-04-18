# sbf-2 QA Walkthrough — Presigned upload URL endpoint

**Story:** sbf-2-presigned-upload-url-endpoint
**Status:** done

## What shipped

- `POST /v1/imports/upload-url` — auth-required endpoint that returns
  a 1-hour presigned S3 PUT URL targeting the new
  `palateful-imports-{env}` bucket (created in sbf-1).
- `AWSService.presign_put_url(s3_key, bucket, content_type,
  content_length, tagging=None, expires_in=3600)` — bucket-explicit
  helper that signs Content-Type / Content-Length / Tagging and
  returns the matching `required_headers` map.
- New error codes 290–294 in `ErrorCode` (`FILE_TOO_LARGE`,
  `UNSUPPORTED_MIME` used by sbf-2; the rest reserved for sbf-3).

## Manual smoke test (when there's a real iOS / Postman client)

There's no app integration yet (Epic 2 will consume this), so manual
verification is API-side only.

### 1. Happy path

```bash
curl -X POST http://localhost:8000/v1/imports/upload-url \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "voice_memo.m4a",
    "mime_type": "audio/mp4",
    "size_bytes": 1048576
  }'
```

Expected:
- 200 status.
- Body: `{upload_url, s3_key, required_headers, expires_at}`.
- `s3_key` matches `^imports/<your-user-uuid>/<random-uuid>\.m4a$`.
- `required_headers` includes `Content-Type: audio/mp4`,
  `Content-Length: 1048576`, `x-amz-tagging: unclaimed=true`.
- `upload_url` host starts with `palateful-imports-dev.s3.` (or the
  env-specific bucket for staging/prod).

### 2. Cap enforcement

```bash
# Oversize: > 100 MiB
curl ... -d '{"filename":"huge.mp4","mime_type":"video/mp4","size_bytes":104857601}'
```
Expected: 413, `error_code: 290` (`FILE_TOO_LARGE`).

```bash
# Zero / negative size
curl ... -d '{"filename":"empty.pdf","mime_type":"application/pdf","size_bytes":0}'
```
Expected: 400, `error_code: 37` (`INVALID_REQUEST`).

### 3. MIME allowlist

```bash
curl ... -d '{"filename":"x.bin","mime_type":"application/octet-stream","size_bytes":1024}'
```
Expected: 400, `error_code: 291` (`UNSUPPORTED_MIME`).

Allowed mimes (round-trip → canonical extension):

| MIME | Extension |
|------|-----------|
| `application/pdf` | pdf |
| `image/jpeg` | jpg |
| `image/png` | png |
| `image/gif` | gif |
| `image/webp` | webp |
| `image/heic` | heic |
| `image/heif` | heif |
| `audio/mpeg` | mp3 |
| `audio/mp4` | m4a |
| `audio/x-m4a` | m4a |
| `audio/wav` | wav |
| `audio/x-wav` | wav |
| `audio/aac` | aac |
| `audio/ogg` | ogg |
| `audio/webm` | weba |
| `video/mp4` | mp4 |
| `video/quicktime` | mov |
| `video/x-m4v` | m4v |
| `video/webm` | webm |
| `text/csv` | csv |
| `application/vnd.ms-excel` | xls |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | xlsx |
| `text/plain` | txt |

### 4. PUT round-trip (when AWS creds are available)

```bash
RESPONSE=$(curl -sS ... -d '{"filename":"clip.mov","mime_type":"video/quicktime","size_bytes":52428800}')
URL=$(echo "$RESPONSE" | jq -r .upload_url)
dd if=/dev/urandom of=/tmp/clip.mov bs=1M count=50

curl -X PUT "$URL" \
  -H "Content-Type: video/quicktime" \
  -H "Content-Length: 52428800" \
  -H "x-amz-tagging: unclaimed=true" \
  --data-binary @/tmp/clip.mov
```

Expected: 200 from S3, ETag header in response. Object visible in
`palateful-imports-dev` bucket under `imports/<user-uuid>/<obj-uuid>.mov`
with the `unclaimed=true` tag (will be reaped by the 24h lifecycle
rule unless sbf-3's `/import` call comes through first and clears it).

If headers don't match what the response promised, S3 returns
`SignatureDoesNotMatch` — the `required_headers` map is the contract
clients must follow.

### 5. Auth gate

Hitting the endpoint without a JWT returns 401/403/422 (FastAPI's
`HTTPBearer` dep returns 422 when the header is absent entirely).

## What's NOT in this story (don't QA here)

- The `/import` endpoint accepting `s3_key` — sbf-3.
- The `unclaimed=true` tag being cleared on successful import — sbf-3.
- HeadObject / `object_not_ready` retry handshake — sbf-3.
- DB unique constraint on `ImportItem.s3_key` — sbf-3.
- Replay (`409 duplicate_import`) — sbf-3.
- ffmpeg / video_file source_type — sbf-4.
- Social URL routing — sbf-5.

## Automated test coverage

```
services/api/tests/test_import.py::TestGetImportUploadUrl   # 10 tests
services/api/tests/test_aws_service.py::TestPresignPutUrl    # 7 tests
```

All pass under `DATABASE_URL=postgresql://test/test poetry run pytest`.
