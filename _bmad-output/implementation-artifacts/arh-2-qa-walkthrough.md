# QA walkthrough — arh-2: Remove over-declared READ_MEDIA_* permissions

## Smoke prerequisites

- Android 13 (API 33) or Android 14 (API 34) emulator — earlier APIs
  never prompted for these permissions, so removing them is a no-op
  there. Only post-13 exercises the intent-flag grant code path.
- Sample image, video, audio, and PDF files accessible from Files /
  Google Photos on the emulator.

## Checklist

- [ ] Install the release AAB. Open Settings → Apps → Palateful →
      Permissions. Confirm `Photos and videos`, `Music and audio` are
      NOT listed.
- [ ] Open Google Photos. Long-press a photo → Share → Palateful.
      Confirm:
  - [ ] Palateful opens.
  - [ ] The share handler copies the photo to the app sandbox and
        routes to the import screen (sae-2 regression surface).
  - [ ] No `SecurityException` in `adb logcat`.
- [ ] Repeat with a video from Google Photos → Share → Palateful. Same
      expectations.
- [ ] Repeat with an audio file from the Files app. Same expectations.
- [ ] Repeat with a PDF from the Files app. Same expectations.
- [ ] Kill and relaunch Palateful, then re-share the same photo a
      second time from a freshly cold-started state (fresh process,
      no cached URI grants). Handler should still succeed — confirms
      the intent-carried grant is honoured every time, not just within
      a single process lifetime.

## Regression surface

- **sae-2 content-aware handler**: all branches (image / video / audio
  / PDF / spreadsheet) must still copy to sandbox and proceed. Watch
  for `Permission denial` or `java.lang.SecurityException` in logcat.
- **sae-3 unsupported-type fallback**: unchanged. Handler only checks
  MIME/extension, not manifest permissions.

## Lint check (runs in CI)

- Manifest is still well-formed XML. No other file references
  `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, or `READ_MEDIA_AUDIO` except
  sae-1 historical docs (acceptable).

## Out of scope

- Pre-API-33 emulator testing (no-op).
- Google Play Pre-Launch Report run — that's a Play Console activity
  owned by `epic-android-play-console-launch`.
