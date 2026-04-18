# QA Walkthrough — sae-1: AndroidManifest MIME + permission expansion

Requires an Android device / emulator with the updated APK installed.
Test on Android 13+ ideally (14/15 if available) to exercise the new
`READ_MEDIA_*` permission path.

## Setup

- [ ] Install the new APK on a clean Android device (uninstall prior
  builds if permissions were previously granted).
- [ ] Keep `adb logcat` running in a terminal to watch for any manifest
  parse warnings on first launch.

## Share-sheet surfacing (Palateful appears)

- [ ] **Photos — JPG**: Open Google Photos, long-press a photo, tap
  Share. Scroll the target list. Palateful should appear.
- [ ] **Files — PDF**: Open Files app, tap any PDF, tap the ⋮ menu →
  Share. Palateful should appear.
- [ ] **WhatsApp — Video**: Play a saved video clip in WhatsApp, tap the
  share glyph. Palateful should appear.
- [ ] **Audio**: From any audio source (Voice Recorder, Files), tap
  Share on an .mp3 / .m4a. Palateful should appear.
- [ ] **Drive — Spreadsheet**: Open a `.csv` or `.xlsx` in Drive, tap
  the ⋮ menu → Send a copy → Share. Palateful should appear.
- [ ] **Chrome — URL**: Share a webpage from Chrome. Palateful should
  still appear (regression — `text/plain` filter preserved).
- [ ] **Notes — Plain text**: Share plain text from Notes / Keep.
  Palateful should appear (regression).

## Share-sheet suppression (expected behavior — we did NOT ship `*/*`)

- [ ] **Drive — `.docx`**: Share a Word document from Drive. Palateful
  should **not** appear. This is intentional — the `*/*` wildcard is
  metrics-gated and not in v1. Users with a legitimate use case route
  the content via Paste Text.

## Multi-select

- [ ] **Photos — 3 JPGs**: Select three photos in Google Photos, tap
  Share. Palateful should appear. (Actual handling of multiple items is
  sae-2 behavior — here we only confirm the share sheet surfaces
  Palateful for `ACTION_SEND_MULTIPLE`.)

## Permissions

- [ ] Run `adb shell dumpsys package com.palateful.app | grep
  READ_MEDIA` — should list `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`,
  `READ_MEDIA_AUDIO`.
- [ ] Share a photo → app launches, no runtime permission prompt. (OS
  grants access via Intent flags transparently.)

## Regression

- [ ] MainActivity export flag still true — launch the app normally
  from the home screen. App opens without an "activity not found"
  error.
- [ ] Auth0 deep link still works: log out, log in. The
  `com.palateful.app` intent filter is preserved.

## Release readiness (human-only)

- [ ] Before merging to `main` for release: update the Play Console
  Data Safety form to disclose `READ_MEDIA_*` and shared-file
  ingestion.
- [ ] Upload an internal track build to Play Console and review the
  Pre-launch report for any new permission warnings. Expected: no new
  warnings (READ_MEDIA_* is a standard permission, not sensitive).
