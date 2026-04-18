<!-- refined via party-mode 2026-04-18 -->
<!-- revised 2026-04-18: dropped Redis import_intent in favor of key-prefix ownership check + DB unique constraint; swapped SSM delivery for standard ECS env var (`S3_IMPORTS_BUCKET`, matching `PARSER_INPUTS_BUCKET`) — no SSM Parameter Store pattern exists in this repo -->
# Epic: Share Backend Foundations (presigned upload + video_file + social URL routing)

## Locked cross-epic decisions (propagate unchanged to Epics 2/3/4)

1. **Single upload contract.** Every file-based share — iOS extension, Android intent, Flutter picker — goes through `POST /v1/imports/upload-url` → direct S3 PUT → `POST /import` with `{s3_key, etag}`. The `file_base64` path is frozen to its current callers (small photos/text inline) and is NOT extended for new source types or new entrypoints.
2. **Ownership via S3 key prefix; replay prevention via DB unique constraint.** The presigned `s3_key` is `imports/{user_id}/{uuid4}.{ext}` — `/import` rejects any key whose prefix doesn't match the current user's id (`403 cross_user_key`). Replay of the same key is blocked by a `UNIQUE` constraint on `ImportItem.s3_key` (the second `/import` with the same key returns `409 duplicate_import`). Redis was considered and dropped — Redis is not deployed in this stack and the key-prefix + unique-column design gives the same properties without new infra.
3. **ETag handshake.** Client PUT captures the S3 `ETag`; `/import` accepts `{s3_key, etag}`; backend runs `HeadObject` and returns **409 `object_not_ready`** if missing. Client retries `/import` up to 3× with 500 ms backoff before surfacing error.
4. **Machine-readable `error_code` on every 4xx.** `file_too_large`, `unsupported_mime`, `object_not_ready`, `cross_user_key`, `duplicate_import`, `jwt_expired`, `rate_limited`. UI layers map to copy; never string-parse.
5. **Sandbox-first for shared payloads** (enforced by Epics 2/3): routes and workers only ever see paths under the app's own sandbox or S3 keys under `imports/{user_id}/...`.

## Overview

This epic lays the backend and infrastructure plumbing that the iOS Share Extension and the Flutter receiving flow both need before they can meaningfully send anything. Today, `POST /v1/recipe-books/{book_id}/import` accepts files only as base64 in the request body — fine for a 2 MB photo, impossible for a 100 MB video. Today, social media URL detection happens inside `extract_recipe_task`, so `ImportItem.source_type` is persisted as `url` for a TikTok share and the Activity Hub has no way to label it "TikTok import" correctly. Today, the worker container has yt-dlp and PyMuPDF but no ffmpeg, so local video files (video from Photos.app) cannot be processed at all.

This epic closes those three gaps without user-visible surface area of its own. It unblocks Epic 2 (iOS extension) and Epic 4 (Flutter receiving UX) to actually deliver files.

## Goal

Backend accepts file-based imports up to 100 MB via presigned S3 upload; accepts local video files and processes them through an ffmpeg → Whisper → text extraction chain; persists the correct `source_type` at creation time for social URLs so downstream UI doesn't have to infer it.

## End-user flow

This epic has no direct end-user surface, but the user-visible result is:

1. User shares an 80 MB TikTok video download from Files.app into Palateful on the next epic's extension. The extension calls `POST /v1/imports/upload-url` and uploads to S3 in ~10 seconds.
2. The extension calls `POST /v1/recipe-books/{book_id}/import` with `source_type: "video_file"` and the returned `s3_key`. Backend enqueues `ParseSourceTask`, which reads the file from S3 and hands off to the new ffmpeg audio-extraction step, then Whisper transcription, then the existing text extractor, then ingredient matching.
3. A few minutes later the user sees a push "Your recipe from the shared video is ready for review" and lands in the Activity Hub on a row labeled with the correct source type.

## Frontend changes

None. All user-facing surface for this epic is delivered via Epic 2 (iOS extension) and Epic 4 (Flutter receiving UX).

## Backend changes

### New endpoint: `POST /v1/imports/upload-url`

- **Auth:** same JWT / user context as other import endpoints.
- **Request body:** `{ filename: str (≤255), mime_type: str, size_bytes: int }`.
- **Response:** `{ upload_url: str (presigned S3 PUT, 1-hour expiry), s3_key: str, expires_at: datetime }`.
- **Validation:** rejects `size_bytes > 100 * 1024 * 1024` with 413 + explicit message. Rejects unknown `mime_type` values outside the allowlist: `application/pdf`, `image/*`, `audio/*`, `video/*`, `text/csv`, `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `text/plain`.
- **S3 key shape:** `imports/{user_id}/{uuid4}.{ext}` where `ext` is derived from `mime_type`. No user-supplied filename in the key (avoids collisions and injection).
- **Presigned PUT condition:** `Content-Length-Range 0, 104857600` so even a signed URL cannot be used to upload >100 MB.

### Updated: `POST /v1/recipe-books/{book_id}/import`

- Adds optional `s3_key: str` field. Mutually exclusive with `file_base64`.
- When `s3_key` is set: the endpoint validates the key matches `imports/{current_user_id}/...` (prevents cross-user read), creates `ImportItem` with `raw_data={"s3_key": s3_key}`, and dispatches `ParseSourceTask` as usual.
- Adds `"video_file"` to the `source_type` pattern regex.
- Social URL detection runs on the input URL (if `source_type == "url"`): if `detect_platform(url)` returns anything non-`WEB`, the endpoint promotes `source_type` to `"video"` before creating the ImportItem. This moves the detection upstream (it currently lives in `extract_recipe_task._extract_single_item`).

### New task path: `ParseSourceTask` for `video_file`

- When `source_type == "video_file"`, the task:
  1. Reads the file from S3 using the `s3_key` from `raw_data`.
  2. Streams it through ffmpeg (`ffmpeg -i input -vn -acodec libmp3lame -b:a 64k output.mp3`) to extract an audio-only track. Max duration enforced at 20 minutes (ffmpeg `-t 1200`).
  3. Uploads the extracted audio to the same `imports/` prefix (`{original_key}.audio.mp3`).
  4. Transitions to `ExtractRecipeTask`, which dispatches to the existing audio-transcription path (`extract_recipe_from_audio`).
- On ffmpeg failure: item → `failed` with `error_code="video_decode_failed"` and `error_message` containing the ffmpeg stderr tail.
- The extracted audio file is deleted from S3 after `CreateRecipeTask` completes or after 7 days via lifecycle policy.

### Updated: `ParseSourceTask` for non-video file-based imports

- When `raw_data["s3_key"]` is present and `source_type ∈ {"audio", "pdf", "spreadsheet"}`, the task reads the file from S3 instead of decoding base64 from request body. The existing transcription / PyMuPDF / csv code paths run unchanged on the bytes.
- The existing base64 path remains for backwards compatibility (small files from the non-share flows).

### Social URL routing moved to endpoint

- `libraries/utils/utils/services/url_classifier.py` already exists (verified in research). The endpoint calls `detect_platform(url)` once at ImportItem creation time. If platform is TikTok / Instagram / YouTube / Pinterest / Facebook, `source_type` is set to `"video"` (matches the existing video-metadata extractor path). Web URLs stay as `"url"`.
- `extract_recipe_task._extract_single_item`'s existing social-URL check is kept as a defensive fallback (e.g., for URLs that the endpoint missed due to classifier drift), but the primary routing is now upstream.
- `ImportJob.source_type` aggregation logic (if any) is unchanged.

### S3 access layer

- `libraries/utils/utils/services/aws.py` (or equivalent) gains a `presign_put_url(s3_key, mime_type, max_size)` helper and a `read_object(s3_key) -> bytes` helper (if not already present). Worker IAM role must have `s3:GetObject` on the new imports bucket (see infra changes).

## Infrastructure changes

### New S3 bucket: `palateful-imports-{env}`

- Terraform module added at `terraform/modules/s3/main.tf` (new block or extension of existing).
- Block public ACLs, enforce TLS, AES-256 encryption (match existing buckets).
- Lifecycle rule: dev = 7 days, prod = 30 days. Expires both raw uploads and ffmpeg-extracted audio.
- CORS rules: `PUT` from the iOS bundle origin (or `*` if using presigned URLs without browser-like CORS — verify AWS requirement).

### IAM

- `batch_job_s3` policy (or equivalent worker role in `terraform/modules/iam/`) extended to include `s3:GetObject` and `s3:DeleteObject` on `arn:aws:s3:::palateful-imports-{env}/*`.
- API task role gains `s3:PutObject` via presigned URL signing (typically requires only key signing capability, not runtime `PutObject`; verify with the existing presigned pattern used by `get_photo_upload_url.py`).

### Worker Dockerfile (`services/worker/Dockerfile`)

- Add `ffmpeg` via `apt-get install -y ffmpeg` in the builder and final stages.
- Verify image size delta stays under +150 MB (LGPL ffmpeg build from Debian repo is ~80 MB + codec libs).
- LGPL-compatible build: default Debian `ffmpeg` package ships under LGPL 2.1+, compatible with commercial use when dynamically linked. Documented in the commit message.

### Secrets / env vars

- No new secrets. `OPENAI_API_KEY` covers Whisper; AWS creds unchanged.
- `.env.example` adds `S3_IMPORTS_BUCKET=palateful-imports-local` for local dev against MinIO or localstack (if used).

## Initial design principles

- **Additive, not replacive.** `file_base64` path stays; `s3_key` is a new option. Small-file flows don't need to change.
- **Upstream source_type promotion is the signal, not downstream inference.** Endpoint decides the source type once; tasks trust it.
- **ffmpeg is a dependency of the worker, not the API.** Keeps the API image lean and the video-file processing cleanly async.
- **Cap enforcement happens at three layers** (request validation, presigned URL signature, and S3 bucket policy if feasible) — defense in depth against a 5 GB video.
- **No new queue.** Existing `palateful-{env}-celery` queue handles video_file tasks; long-running audio transcription already runs there for the social URL path.

## File structure (anticipated)

### Backend
- `services/api/src/api/v1/import_job/upload_url.py` — NEW: `POST /v1/imports/upload-url` endpoint class.
- `services/api/src/api/v1/import_job/start_import.py` — MODIFY: add `s3_key`, `video_file`, social URL promotion, cross-user-key validation.
- `services/api/src/routers/v1/import_router.py` — MODIFY: register the new upload-url route.
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py` — MODIFY: S3 read path for audio/pdf/spreadsheet; new `_parse_video_file` branch.
- `libraries/utils/utils/services/recipe_extractors/video_file_extractor.py` — NEW: ffmpeg wrapper; audio extraction; duration cap.
- `libraries/utils/utils/services/aws.py` — MODIFY: `presign_put_url`, `read_object`, `delete_object` helpers if missing.
- `libraries/utils/utils/services/url_classifier.py` — VERIFY/EXTEND: used by both endpoint and extract task.
- `services/api/tests/test_import.py` — MODIFY: cover presigned upload, s3_key path, video_file source_type, social URL promotion.

### Infrastructure
- `terraform/modules/s3/main.tf` — MODIFY or add new block for `imports` bucket.
- `terraform/modules/iam/main.tf` — MODIFY: extend worker and API role policies.
- `services/worker/Dockerfile` — MODIFY: add ffmpeg to builder + final stages.
- `.env.example` — MODIFY: document S3 imports bucket var.

## Stories

### Story 1: `sbf-1` — New imports S3 bucket + IAM wiring

**AC:**
- `palateful-imports-{env}` bucket exists in dev and prod via Terraform with block-public-acls, AES-256 encryption, 7-day (dev) / 30-day (prod) lifecycle on both raw uploads and `*.audio.mp3` derivatives.
- Additional 24 h lifecycle rule on objects with `x-amz-meta-unclaimed=true` (mid-upload leaks; see `sbf-3`).
- Worker role has `s3:GetObject` + `s3:DeleteObject` on the bucket.
- API role can sign presigned PUT URLs for the bucket.
- Bucket name exposed to API + worker task definitions via the plain ECS environment variable `S3_IMPORTS_BUCKET` (mirrors `PARSER_INPUTS_BUCKET`; no SSM Parameter Store integration exists in this repo, so we don't introduce one here). `config.py` falls back to `f"palateful-imports-{env}"` when unset so local dev works without touching terraform. `terraform plan` shows zero drift after apply in dev.
- CORS rules verified for iOS and Android presigned-PUT flows (the extension uses `URLSession`, not browser XHR; configure minimally).

### Story 2: `sbf-2` — Presigned upload URL endpoint

**AC:**
- `POST /v1/imports/upload-url` accepts `{filename, mime_type, size_bytes}`. Response shape: `{upload_url, s3_key, required_headers: {Content-Type, ...}, expires_at}`. The `required_headers` map names every signed header so clients know exactly what to send — missing this has caused signature mismatches in similar flows.
- Presigned PUT condition: `Content-Length-Range 0, 104857600`.
- Rejects `size_bytes > 100 MB` with `413 {error_code: "file_too_large"}`.
- Rejects unknown MIME types with `400 {error_code: "unsupported_mime"}`.
- `s3_key` matches regex `^imports/[0-9a-f-]{36}/[0-9a-f-]{36}\.[a-z0-9]{2,5}$` (user UUID + object UUID — no raw user identifiers beyond the authenticated user's id).
- Ownership is encoded in the key itself — no server-side intent record. `/import` enforces it in `sbf-3` by requiring the `s3_key` to start with `imports/{current_user_id}/`.
- A dev spike (can be a test fixture) proves `URLSession.uploadTask(with:fromFile:)` round-trips a 50 MB fixture through the signed URL without signature mismatch — catches header/codec interplay before Epic 2 consumes the endpoint.
- Unit + integration tests: valid request, oversize rejection, bad MIME, expiry, correct key shape.

### Story 3: `sbf-3` — `s3_key` import path for existing source_types (audio / pdf / spreadsheet)

**AC:**
- `POST /v1/recipe-books/{id}/import` accepts `{s3_key, etag}` (mutually exclusive with `file_base64`). `file_base64` path unchanged — frozen to current callers.
- Endpoint enforces ownership by string check: `s3_key` must start with `imports/{current_user.id}/`. `403 {error_code: "cross_user_key"}` on mismatch.
- Replay prevention via DB: `ImportItem` gets a new nullable `s3_key` column with a partial unique index (`UNIQUE (s3_key) WHERE s3_key IS NOT NULL`). A second `/import` call with the same key returns `409 {error_code: "duplicate_import"}`. Migration lives in `services/migrator/migrations/versions/`.
- Endpoint runs `HeadObject(s3_key)`; `409 {error_code: "object_not_ready"}` if missing — client retries per cross-epic handshake.
- `ImportItem.raw_data` persists `{s3_key, original_filename, mime_type, etag}` for support/debugging; the `s3_key` is duplicated into the dedicated column for the unique constraint.
- `ParseSourceTask` reads from S3 when `s3_key` present; base64 path still works.
- Per-user rate limit: `imports_per_user_per_hour ≤ 30` at the endpoint level, using the existing in-memory sliding-window pattern (see `services/api/src/api/v1/admin/send_test_push.py:30` for the precedent) scoped by `user.id`. `429 {error_code: "rate_limited"}` above the cap. Acceptable for current 2-instance API deployment (worst case: 60/hr/user across both instances); revisit when Redis lands.
- End-to-end test: presign → PUT → import → recipe created for audio and PDF source_types. Replay test: same `/import` payload twice → second returns 409.

### Story 4: `sbf-4` — ffmpeg in worker + `video_file` source_type

**AC:**
- Worker Dockerfile installs ffmpeg; image size delta ≤ +150 MB; `ffmpeg -version` works inside the container.
- Supported codec matrix documented in `docs/import-pipeline.md`: at minimum H.264 / AAC / MP3 / AAC-LC. H.265 explicitly out of scope (patent concerns with default Debian build).
- `source_type="video_file"` accepted by the import endpoint.
- `ParseSourceTask._parse_video_file` extracts audio with ffmpeg, caps at 20 minutes, uploads as `{key}.audio.mp3`, then hands off to the existing audio-transcription extractor.
- ffmpeg runs in its own process group (`subprocess.Popen(..., preexec_fn=os.setsid)`); Celery `soft_time_limit=1500` sends `SIGTERM` to the process group (not just the parent) so ECS drain doesn't leave zombies.
- Stream processing: ffmpeg output piped directly to the S3 uploader — never writes the full extracted audio to `/tmp`. Prevents disk exhaustion under concurrent jobs.
- Failure paths: ffmpeg error → item `failed` with `error_code="video_decode_failed"` + ffmpeg stderr tail in `error_message`. Fixtures cover: (a) video with no audio track, (b) audio-only m4a misfiled as video, (c) 21-minute video (cap boundary), (d) corrupt header.
- All fixtures committed under `libraries/utils/utils/tests/fixtures/`.

### Story 5: `sbf-5` — Social URL routing promoted to endpoint

**AC:**
- `POST /v1/recipe-books/{id}/import` with `source_type="url"` and a TikTok/Instagram/YouTube/Pinterest/Facebook URL promotes `ImportItem.source_type` to `"video"` at creation time.
- `ImportItem.raw_data.detected_platform` populated with one of `"tiktok"`, `"instagram"`, `"youtube"`, `"pinterest"`, `"facebook"` — Activity Hub (and `epic-activity-hub-redesign`) uses this to label rows and differentiates from new `"video_file"` items via presence of `s3_key`.
- Web URLs stay as `"url"`.
- `extract_recipe_task`'s existing social check remains as defensive fallback (no regression tests broken).
- Unit tests on `url_classifier.detect_platform` cover all five platforms + the web default.

## Dependencies

- None upstream. Can start immediately.
- Blocks Epic 2 (iOS Share Extension) — that epic's upload step calls `/v1/imports/upload-url`.
- Blocks Epic 4 (Universal Receiving UX) — the Flutter screens' pre-filled path relies on `s3_key` being accepted for file-based source_types.

## Risks surfaced in party-mode (tracked, mitigated in ACs)

- **Presign-to-import race / orphan uploads:** extension crashes between PUT and `/import`. Mitigated by key-prefix ownership check + DB unique constraint on `ImportItem.s3_key` (no second-claim possible) + 24 h S3 lifecycle rule on objects tagged `unclaimed=true` (API tags on presign, clears on success).
- **ECS SIGTERM mid-ffmpeg:** zombie subprocesses holding `/tmp`. Mitigated in `sbf-4` via process group signaling.
- **Cost tail on abuse:** 30 imports/hour rate limit in `sbf-3`; additional cost observability via existing `ImportJob.total_ai_cost_cents` already tracks AI spend.
- **Signature mismatch on `URLSession` upload:** dev spike + `required_headers` in response both address it in `sbf-2`.
- **Temp disk exhaustion:** stream-through-pipe for ffmpeg output in `sbf-4`.
- **`source_type` labeling collision** (social `"video"` vs new `"video_file"`): disambiguated by presence of `s3_key` and `raw_data.detected_platform` (`sbf-5`).

## Open questions for the user

None. The backend contract is fully specified by the locked decisions plus the cross-epic handshake above.
