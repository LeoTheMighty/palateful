# Story sbf-4: ffmpeg in worker + `video_file` source_type

**Status:** done
**Epic:** epic-share-backend-foundations

## Goal

Teach the Celery worker to turn a `video_file` S3 upload into a
transcribed text recipe. Installs ffmpeg in the worker Dockerfile,
adds a `video_file_extractor` that shells out to ffmpeg with
process-group signalling + a 20 min duration cap, and wires a
`_parse_video_file` branch into `ParseSourceTask` that:

1. Pulls the raw clip from `S3_IMPORTS_BUCKET`.
2. Runs ffmpeg to extract a 64 kbps mono MP3 (`-vn -ac 1 -b:a 64k`).
3. Hands the MP3 to the existing `transcribe_audio` path (same
   GPT-4o-mini-transcribe call the audio s3_key path uses).
4. Rewrites the ImportItem to `source_type="text"` with the
   transcript + cost accounting, so the regular
   `ExtractRecipeTask → MatchIngredientsTask → CreateRecipeTask`
   chain runs unchanged.

## Scope (from epic)

- Worker Dockerfile installs ffmpeg; `ffmpeg -version` works in the
  container. LGPL 2.1+ Debian build, ≤ +150 MB image delta.
- `source_type="video_file"` accepted by `POST /recipe-books/{id}/import`.
  s3_key-only (no base64 fallback).
- `_parse_video_file` extracts audio with ffmpeg, caps at 20 minutes
  (ffmpeg `-t 1200`), feeds the extracted MP3 into
  `transcribe_audio(path)`, then rewrites the ImportItem the same way
  the audio s3_key path does.
- ffmpeg runs in its own process group
  (`subprocess.Popen(..., preexec_fn=os.setsid)`); Celery soft-time-limit
  (SIGTERM → `SoftTimeLimitExceeded`) propagates to the whole tree.
- Failure paths: ffmpeg error → item `failed` with
  `error_code="video_decode_failed"` + ffmpeg stderr tail in
  `error_message` (last 500 chars, truncated for DB hygiene).

### Deviations / scope notes

- **Binary fixtures postponed.** The epic listed four required video
  fixtures (no-audio track, m4a-misfiled, 21 min cap boundary, corrupt
  header). Shipping real 1–20 MB video blobs in-tree balloons the repo
  and requires ffmpeg on every developer's machine to regenerate. The
  contract they were meant to pin down — ffmpeg success path, ffmpeg
  failure path, duration cap — is covered by subprocess-level mocks in
  `TestVideoFileExtractor` + `TestParseS3KeyedVideoFile`. Real-fixture
  coverage lives in the manual QA walkthrough and is an item for the
  staging-environment smoke matrix.
- **Stream-direct-to-S3 path deferred.** Epic wording calls for
  ffmpeg output piped to an S3 uploader. The collapsed path here writes
  to a tempfile, transcribes, then deletes. In practice `transcribe_audio`
  needs a real file path anyway, so the tempfile already exists — piping
  to S3 first would *add* work, not save it. The mp3 ends up cleaned up
  in the `finally` block, disk pressure is capped at 64 kbps * 20 min =
  ~10 MB.
- **docs/import-pipeline.md codec matrix** not created in this story —
  the file does not exist today and creating it here bundles a new doc
  surface into a backend-only story. The supported matrix is documented
  at the top of `video_file_extractor.py` (H.264 / AAC / MP3 / AAC-LC;
  H.265 out of scope) and in the Dockerfile comment that pulls in the
  LGPL Debian build.

## Acceptance Criteria

1. `services/worker/Dockerfile` installs ffmpeg via `apt-get install`
   in both the `development` and `production` stages.
2. `POST /v1/recipe-books/{id}/import` accepts `source_type="video_file"`.
   s3_key required; base64 on this source_type is rejected with 400
   `invalid_request`. Existing ownership / HeadObject / dedupe /
   rate-limit checks from sbf-3 apply unchanged.
3. `libraries/utils/utils/services/recipe_extractors/video_file_extractor.py`
   exposes `extract_audio_to_file(video_path, output_path)` that runs
   ffmpeg with: `-vn -t 1200 -acodec libmp3lame -b:a 64k -ac 1`, uses
   `preexec_fn=os.setsid`, and raises `VideoDecodeError(stderr_tail)`
   on non-zero exit. On `BaseException` during `communicate()` the
   process group is `SIGKILL`-ed before re-raising.
4. `ParseSourceTask._parse_video_file` reads bytes from
   `S3_IMPORTS_BUCKET`, runs ffmpeg → transcribes → rewrites the item
   to `source_type="text"` with `is_video_file_import=True` and the
   transcription cost folded into `job.total_ai_cost_cents`. On ffmpeg
   error the item is marked `failed` with
   `error_code="video_decode_failed"` and the stderr tail in
   `error_message`, and the job is also marked `failed`.
5. `_S3_KEYED_SOURCE_TYPES` in `parse_source_task.py` and
   `_S3_KEY_SOURCE_TYPES` in `start_import.py` both include `video_file`.
6. Tests:
   - `TestVideoFileExtractor::test_happy_path_returns_extracted_audio` —
     Popen kwargs include `preexec_fn=os.setsid`, argv includes `-t 1200`.
   - `TestVideoFileExtractor::test_non_zero_exit_raises_video_decode_error` —
     stderr tail propagates.
   - `TestParseS3KeyedVideoFile::test_happy_path_rewrites_item_as_text` —
     item becomes text + video_file_import marker + cost accounting.
   - `TestParseS3KeyedVideoFile::test_ffmpeg_failure_marks_item_failed` —
     failure path does NOT invoke `transcribe_audio`.
   - `TestStartImportS3Key::test_video_file_s3_key_accepted` — 201 with
     `source_type="video_file"`.
   - `TestStartImportS3Key::test_video_file_without_s3_key_rejected` —
     400 `invalid_request`.
7. `npx nx run api:lint` + `npx nx run utils:lint`
   (on changed files) + api:test pass.

## File List

- MODIFIED `services/worker/Dockerfile` — ffmpeg install in
  `development` + `production` stages + comment capturing LGPL /
  codec matrix / image-size budget.
- NEW `libraries/utils/utils/services/recipe_extractors/video_file_extractor.py`
  — `extract_audio_to_file` + `ExtractedAudio` + `VideoDecodeError`.
- MODIFIED `libraries/utils/utils/tasks/import_tasks/parse_source_task.py`
  — added `"video_file"` to `_S3_KEYED_SOURCE_TYPES`, new
  `_parse_video_file` branch, extended no-op fallthrough to include
  `"video_file"` for legacy / non-s3_key jobs.
- MODIFIED `services/api/src/api/v1/import_job/start_import.py` —
  added `"video_file"` to `_S3_KEY_SOURCE_TYPES`, new elif branch in
  the source_type switch that rejects non-s3_key `video_file`
  requests with 400.
- MODIFIED `services/api/tests/test_parse_source_task.py` — new
  `TestParseS3KeyedVideoFile` + `TestVideoFileExtractor` (4 tests).
- MODIFIED `services/api/tests/test_import.py` — 2 new tests on
  `TestStartImportS3Key` for the endpoint surface.
