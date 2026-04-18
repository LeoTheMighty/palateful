# Story sae-1: AndroidManifest MIME + permission expansion

**Status:** done
**Epic:** epic-share-android-entrypoint

## Goal

Make Palateful appear in the Android share sheet for every MIME type the
backend can handle, and declare the Android 13+ scoped media permissions
needed to read shared bytes without `SecurityException`.

## Scope (from epic)

- AndroidManifest declares per-MIME `<intent-filter>` blocks for both
  `ACTION_SEND` and `ACTION_SEND_MULTIPLE` across: `image/*`, `video/*`,
  `audio/*`, `application/pdf`, `text/csv`, `application/vnd.ms-excel`,
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- Preserve existing `text/plain`/`text/*` filters (cover URL-shared-as-text
  from Chrome).
- **No `*/*` wildcard in v1** — metrics-gated; reopened only if sae-3
  telemetry shows >5% of shares are legitimate-but-unknown.
- Declare `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO`
  permissions (Android 13+). No runtime prompt needed — OS grants read
  access via Intent flags when user picks Palateful as share target.
- `android:exported="true"` on MainActivity was already set (regression
  bullet — verified unchanged).

## Implementation

Edited only `app/android/app/src/main/AndroidManifest.xml`:

1. Added three `<uses-permission>` entries at top of manifest for the
   `READ_MEDIA_*` trio with an explanatory comment.
2. After the existing `text/plain` + `text/*` filters, appended 14 new
   `<intent-filter>` blocks — one `SEND` + one `SEND_MULTIPLE` per MIME
   — grouped by category for readability. Separate blocks (not combined
   `<data>` children) because several Samsung and Xiaomi OEMs skip
   combined filters when ranking share targets.

Debug and profile manifests (`app/android/app/src/{debug,profile}/`)
were left unchanged — they are overlays and don't need the intent
filters.

## File List

- Modified: `app/android/app/src/main/AndroidManifest.xml`

## QA Checklist

See `_bmad-output/implementation-artifacts/sae-1-qa-walkthrough.md` for
the standalone walkthrough. Items here grouped by AC:

### AC — MIME expansion
- [ ] Share a JPG from Google Photos → Palateful appears in share sheet.
- [ ] Share a PDF from Files app → Palateful appears.
- [ ] Share a video from WhatsApp → Palateful appears.
- [ ] Share an MP3 from any audio source → Palateful appears.
- [ ] Share a CSV / XLSX via Drive → Palateful appears.
- [ ] Share plain text from Notes → Palateful appears (regression).
- [ ] Share a URL from Chrome → Palateful appears (regression).

### AC — Multi-select
- [ ] Select 3 JPGs in Google Photos, tap Share → Palateful appears.

### AC — `*/*` wildcard NOT shipped
- [ ] Share a `.docx` from Drive → Palateful does **not** appear in
  share sheet (will be handled via sae-3 unsupported flow only once
  `*/*` is unlocked by telemetry).

### AC — Permissions
- [ ] After install, `adb shell dumpsys package com.palateful.app | grep
  permission` lists `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`,
  `READ_MEDIA_AUDIO`.
- [ ] No runtime permission prompt appears when sharing from Photos.

### AC — Exported activity
- [ ] MainActivity remains `android:exported="true"` (no regression).

### Release readiness (human-only, tracked)
- [ ] Play Console Data Safety form updated to disclose `READ_MEDIA_*`
  and shared-file ingestion (human action).
- [ ] Pre-launch report reviewed for new permission warnings before
  merge (human action).

## Notes

- No Flutter / Dart code touched in this story. The Flutter handler
  rewrite lives in sae-2.
- Crashlytics `share_intent_mime` tag — listed under sae-1 in the epic
  but only reachable from the copy-to-sandbox step implemented in
  sae-2. Implemented there.
