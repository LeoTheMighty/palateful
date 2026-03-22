# Story Media.4: Audio File Import (Voice Memos)

Status: done

## Story

As a user,
I want to import a voice recording (voice memo, audio message) of someone dictating a recipe,
so that I can capture grandma's recipes or save audio recipes shared by friends.

## Acceptance Criteria

1. Audio import option available in Add Recipe sheet under "More Options" (as "Voice Memo")
2. File picker accepts audio files: `.m4a`, `.mp3`, `.wav`, `.aac`, `.ogg`
3. Audio is uploaded to S3 and transcribed via GPT-4o-mini Transcribe
4. Transcript is fed to `extract_recipe_from_text()` for structuring
5. Maximum audio length: 10 minutes
6. Progress: "Uploading..." → "Transcribing..." → "Extracting recipe..." → "Recipe ready!"
7. Audio file deleted from S3 after transcription
8. If transcription yields no recipe content: "Couldn't find a recipe in this recording" with "Edit transcript" option
9. Activity entry created for audio imports
10. Share sheet accepts audio files and routes to this flow

## Tasks / Subtasks

- [x] Task 1: Backend — Audio import endpoint (AC: #3, #5, #7, #9)
  - [x] Accept audio uploads via existing file import endpoint
  - [x] Detect `file_type: "audio"` by MIME type or extension
  - [x] Upload to S3 with auto-expiry (24 hours)
  - [x] Validate duration ≤ 10 minutes (use ffprobe or similar)
  - [x] Route to `AudioExtractor.transcribe()` from Story 2
  - [x] Feed transcript to `extract_recipe_from_text()`
  - [x] Delete S3 file after transcription
  - [x] Create activity entries

- [x] Task 2: Flutter — Audio import screen (AC: #1, #2, #6, #8)
  - [x] Create `app/lib/features/recipes/add_recipe/audio_import_screen.dart`
  - [x] File picker filtered for audio MIME types
  - [x] Upload progress indicator
  - [x] Staged progress: Uploading → Transcribing → Extracting
  - [x] On success: navigate to import review
  - [x] On failure: show transcript text in an editable field, let user fix and re-extract

- [x] Task 3: Share sheet routing (AC: #10)
  - [x] Update `_handleSharedFiles` in main.dart (should already handle audio from Import.8)
  - [x] Ensure audio files route to the audio import screen
  - [x] Verify iOS share extension accepts audio MIME types

## Dev Notes

- This story is intentionally small because it reuses Whisper/Transcribe from Story 2
- The `AudioExtractor` from Story 2 does the heavy lifting — this just adds the file picker + upload flow
- "Edit transcript" on failure is a nice fallback — user can fix misheard words then re-extract
- Voice memos are typically .m4a on iOS — ensure this format is supported
- This is a genuinely novel feature — no major recipe app offers audio import
- Marketing angle: "Record grandma's recipes before they're lost"

### References

- [Investigation: 11-universal-media-import.md — Audio section]
- [Epic: epic-media-import.md]
