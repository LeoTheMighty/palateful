# sbf-4 QA Walkthrough — ffmpeg in worker + video_file source_type

**Story:** sbf-4-ffmpeg-in-worker-and-video-file-source-type
**Status:** done

## What shipped

- Worker container can decode videos: `ffmpeg` present in both
  `development` and `production` stages of `services/worker/Dockerfile`.
- `POST /v1/recipe-books/{id}/import` accepts
  `source_type="video_file"` with an s3_key — same ownership /
  HeadObject / dedupe / rate-limit checks as sbf-3.
- `ParseSourceTask._parse_video_file` reads the clip from
  `S3_IMPORTS_BUCKET`, extracts a 64 kbps mono MP3 via ffmpeg with a
  20 min cap, transcribes with GPT-4o-mini-transcribe, and rewrites
  the ImportItem as a text item so the regular extraction +
  ingredient-matching pipeline takes over.
- ffmpeg runs in its own process group (`os.setsid`). Celery's
  `soft_time_limit` signals the whole tree; a `BaseException` in
  `communicate()` SIGKILLs the group before re-raising.
- Failure path: ffmpeg non-zero exit → item `failed`,
  `error_code="video_decode_failed"`, `error_message` carries the last
  500 chars of ffmpeg stderr.

## Manual smoke test (staging, real AWS)

The worker needs `S3_IMPORTS_BUCKET`, an AWS role with `s3:GetObject`
on that bucket, and `OPENAI_API_KEY` (for Whisper). Prereqs: sbf-2
presign endpoint + sbf-3 /import + a 50–80 MB `.mp4` with an audio
track.

```bash
# Step 1: presign (sbf-2)
PRESIGN=$(curl -sS -X POST $API/v1/imports/upload-url \
  -H "Authorization: Bearer $JWT" \
  -d '{"filename":"clip.mp4","mime_type":"video/mp4","size_bytes":52428800}')
URL=$(echo "$PRESIGN" | jq -r .upload_url)
S3_KEY=$(echo "$PRESIGN" | jq -r .s3_key)

# Step 2: upload (signed PUT)
curl -X PUT "$URL" \
  -H "Content-Type: video/mp4" \
  -H "Content-Length: 52428800" \
  -H "x-amz-tagging: unclaimed=true" \
  --data-binary @/tmp/clip.mp4

# Step 3: claim it as a video_file
curl -X POST $API/v1/recipe-books/$BOOK_ID/import \
  -H "Authorization: Bearer $JWT" \
  -d "{\"source_type\":\"video_file\",\"s3_key\":\"$S3_KEY\",\"mime_type\":\"video/mp4\",\"file_name\":\"clip.mp4\"}"
```

### Expected

- 201 from `/import` with `source_type: "video_file"`.
- Within ~30s, worker logs show `ffmpeg` was invoked, then
  `transcribe_audio` returned a cost.
- `import_items.{id}`:
  - `source_type` flips from `video_file` → `text`.
  - `raw_data.text` = transcript.
  - `raw_data.is_video_file_import = true`.
  - `raw_data.transcription_cost_cents` > 0.
  - `import_jobs.{job_id}.total_ai_cost_cents` includes that cent total.
- Activity Hub row shows "Importing from video" (copy from the
  aggregate label path — refinement for sbf-5 / Activity Hub redesign).

## Failure-path smoke tests

### 1. Broken video (corrupt header)

Pre-PUT a file that isn't actually video (e.g. `head -c 4096 /dev/urandom >
fake.mp4`) and claim it. ffmpeg will non-zero. Expect:

- Worker marks the item `failed`,
  `error_code="video_decode_failed"`,
  `error_message` contains "Invalid data found" (or similar ffmpeg tail).
- `import_jobs.{id}.status` = `failed`.

### 2. Audio-only misfiled as video (m4a with no video track)

Upload an audio-only m4a under `mime_type=video/x-m4v`. ffmpeg with
`-vn` on an audio-only input succeeds (it just re-encodes the existing
audio). Expect: same happy path as the .mp4 case — transcript lands,
cost tracked, no user-visible error.

### 3. Long clip (>20 min)

Upload a 25 min video. ffmpeg `-t 1200` caps the output at 20 min so
Whisper never sees minutes 21–25. Expect: transcript covers the first
20 min only; no error, no billing beyond 20 min of transcription.

### 4. ECS drain mid-decode

Hit the worker with a long clip, then `aws ecs stop-task`. The Celery
soft-time-limit fires `SIGTERM` and the process-group handler SIGKILLs
ffmpeg. Expect: no zombie ffmpeg in the container, no
half-written `.mp3` in `/tmp` of the next task run.

## What's NOT in this story (don't QA here)

- Social URL routing (TikTok / Instagram / YouTube / Pinterest /
  Facebook promotion to `video` source_type) — sbf-5.
- Real fixture coverage — committed-binary fixtures are deferred per
  the story's scope note; subprocess mocks cover the contract.
- docs/import-pipeline.md codec matrix doc — not in repo today;
  supported codec list lives at top of `video_file_extractor.py`.

## Automated test coverage

```
services/api/tests/test_parse_source_task.py::TestParseS3KeyedVideoFile     # 2 tests
services/api/tests/test_parse_source_task.py::TestVideoFileExtractor        # 2 tests
services/api/tests/test_import.py::TestStartImportS3Key::test_video_file_*  # 2 tests
```

All pass under `DATABASE_URL=postgresql://test/test poetry run pytest`.
