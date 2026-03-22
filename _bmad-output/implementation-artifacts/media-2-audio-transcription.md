# Story Media.2: Audio Transcription Fallback for Videos

Status: done

## Story

As a user,
I want the app to transcribe the audio of a video when there are no written captions or description,
so that I can save recipes from cooking videos where the chef speaks the recipe but doesn't write it down.

## Acceptance Criteria

1. When video metadata extraction (Story 1) finds no recipe content, the system automatically downloads the audio track
2. Audio is transcribed using OpenAI GPT-4o-mini Transcribe API ($0.003/min)
3. Transcript is fed to `extract_recipe_from_text()` for structuring
4. Maximum audio length: 10 minutes (prevents runaway costs)
5. Progress shows additional stages: "Downloading audio..." → "Transcribing..." → "Extracting recipe..."
6. If transcription also yields no recipe content, show "Couldn't find a recipe in this video" with "Paste text instead" option
7. Audio files are temporary — deleted from S3 after transcription completes
8. Cost tracking: transcription cost recorded on ImportItem metadata

## Tasks / Subtasks

- [x] Task 1: Backend — Audio download via yt-dlp (AC: #1, #7)
  - [x] Add method to `VideoMetadataExtractor`: `download_audio(url, output_path)`
  - [x] Download audio-only using yt-dlp with `format: 'bestaudio/best'` + ffmpeg postprocessor to mp3
  - [x] Upload to S3 temporarily
  - [x] Enforce 10-minute max duration check (from metadata) before downloading

- [x] Task 2: Backend — Whisper/GPT-4o-mini Transcribe integration (AC: #2, #8)
  - [x] Create `libraries/utils/utils/services/recipe_extractors/audio_extractor.py`
  - [x] `AudioExtractor.transcribe(audio_s3_key)` → downloads from S3, sends to OpenAI Transcribe API
  - [x] Use `gpt-4o-mini-transcribe` model ($0.003/min, cheaper than Whisper)
  - [x] Return transcript text
  - [x] Track cost on ImportItem: `metadata.transcription_cost = duration_minutes * 0.003`

- [x] Task 3: Backend — Wire fallback into ExtractRecipeTask (AC: #1, #3, #6)
  - [x] In `_extract_single_item`: when `has_recipe_content()` returns False for video metadata:
    - Check video duration ≤ 10 minutes
    - Download audio via `download_audio()`
    - Transcribe via `AudioExtractor.transcribe()`
    - Run `has_recipe_content()` on transcript
    - If recipe content found → `extract_recipe_from_text(transcript)`
    - If still no content → flag item as "no_recipe_found" with user-facing message
  - [x] Track `extractor_used: "video_audio_transcript"` on ImportItem
  - [x] Clean up S3 audio file after transcription

- [x] Task 4: Flutter — Extended progress stages (AC: #5, #6)
  - [x] Update video import progress UI to show audio-specific stages
  - [x] "No written recipe found → Downloading audio..." transition
  - [x] On final failure: "Couldn't find a recipe in this video" with:
    - "Paste recipe text" button → text paste screen
    - "Try a different link" button → back to URL input

- [x] Task 5: Update dependencies (AC: #2)
  - [x] Ensure `openai` package version supports transcription API
  - [x] Add `ffmpeg` to worker Docker image if not already present (needed for audio extraction)

## Dev Notes

- GPT-4o-mini Transcribe ($0.003/min) is 50% cheaper than Whisper ($0.006/min) — use it as default
- Average cooking video is 1-5 minutes → $0.003-0.015 per transcription
- The 10-minute cap prevents a 2-hour podcast clip from costing $0.60
- Audio files are ephemeral — delete from S3 immediately after transcription
- This is the Tier 2 fallback from the investigation — only triggered when Tier 1 (metadata) fails
- The `openai` Python package already supports transcription: `client.audio.transcriptions.create()`

### References

- [Investigation: 11-universal-media-import.md — Audio section + Video Tier 2]
- [Epic: epic-media-import.md]
