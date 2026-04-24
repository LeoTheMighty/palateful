<!-- refined via party-mode 2026-04-18 -->
# Epic: Android Share Entry Point — accept any MIME type

## Locked cross-epic decisions (inherited — do not re-litigate)

1. **Single upload contract** (applies to file-based shares that reach the receiving screen): presigned PUT → `/import` with `{s3_key, etag}`. Owned by Epic 1.
2. **Sandbox-first rule:** `_handleSharedFiles` copies the payload to `getApplicationDocumentsDirectory()/shared_inbox/<uuid>.<ext>` before any navigation; routes and screens only see the sandbox path, never a content URI or OS temp path. This epic implements the rule.
3. **Machine-readable error codes** — Epic 4's receiving screen maps each code to copy; Android's job is just to deliver the sandboxed path.

## Added by this workshop

- **`*/*` wildcard is NOT shipped in v1.** We ship the concrete MIME list (`image/*`, `video/*`, `audio/*`, `application/pdf`, `text/csv`, spreadsheet types, preserved `text/plain`/`text/*`). `*/*` is metrics-gated — reopened only if `sae-3` unsupported telemetry shows >5% of share intents are legitimate-but-unknown.
- **`ACTION_SEND_MULTIPLE` intent filters added alongside `ACTION_SEND`** — otherwise multi-share from Google Photos never hands the payload to Palateful and the "first item + snackbar" behavior is unreachable.
- **URL-in-text sniffing is gated** to shares where `mime == text/plain` AND payload ≤ 4 KB AND no `SharedMediaFile.path` points to a file on disk. Prevents hijacking users who legitimately have a URL in their scratchpad.
- **Auth race on cold-start:** `getInitialMedia()` can resolve before `AuthService` rehydrates. Payload persisted to `SharedPreferences` under `pending_share_payload` and replayed on first successful auth.

## Overview

On Android today, Palateful appears in the share sheet only for shares with MIME type `text/plain` or `text/*` (per `app/android/app/src/main/AndroidManifest.xml` intent filters). That covers text notes and URLs-as-text, but it misses photos, PDFs, videos, and audio files. `_handleSharedFiles` in `app/lib/main.dart:215-253` already has extension-based routing for those types, but the dead code never runs because the OS never hands those MIME types to Palateful.

This epic expands the manifest, adds Android 13+ runtime permissions, and rewrites the Flutter handler to be content-aware (MIME + extension + content prefix) so a `.txt` file containing a recipe URL routes correctly, not to the paste screen.

## Goal

User taps Share on Android from any app — Photos, Files, Chrome, Instagram, WhatsApp — and Palateful appears as a target for every MIME type the backend can handle. The app opens to the receiving landing screen (from Epic 4), which routes to the right import flow.

## End-user flow

### Flow A — User shares a photo from Google Photos

1. User long-presses a recipe photo in Google Photos and taps Share.
2. Android share sheet opens. Palateful appears with its app icon in the list of targets.
3. User taps Palateful. If Palateful isn't running, it cold-launches; if it is, it's brought to foreground.
4. The main activity receives `android.intent.action.SEND` with `type="image/jpeg"` and the content URI in `Intent.EXTRA_STREAM`.
5. `receive_sharing_intent` forwards the path to Flutter. `_handleSharedFiles` detects `image/jpeg` MIME, routes to `/recipes/add/receive` (Epic 4's landing screen), which then routes to `/recipes/add/photo?path=...`.
6. Photo capture screen opens with the shared image pre-selected (file picker skipped, per Epic 4).
7. User confirms, import starts, Activity Hub shows the job.

### Flow B — User shares a PDF from Files.app

1. User taps Share on a recipe PDF.
2. Palateful appears. User taps it.
3. Same as Flow A but the MIME is `application/pdf` → `/recipes/add/pdf?path=...`.

### Flow C — User shares a video from WhatsApp

1. User taps Share on a recipe video clip saved in WhatsApp.
2. Palateful appears. User taps it.
3. MIME is `video/mp4` → `/recipes/add/receive` → (Epic 4 detects `video_file` source_type) → `/recipes/add/video?path=...`.
4. Video screen uploads via presigned S3 PUT (Epic 1's endpoint).

### Flow D — User shares a URL as text from Chrome

1. User taps Share on a webpage in Chrome.
2. Palateful appears (existing `text/plain` behavior).
3. Flutter's `_handleSharedFiles` extracts the URL from text and routes to `/recipes/add/share?url=...` — existing behavior, preserved.

### Flow E — User shares a `.txt` file with a URL inside

1. User shares `recipe-url.txt` whose content is `https://allrecipes.com/foo`.
2. MIME is `text/plain`. Current behavior would route to paste screen. New content-aware behavior reads the first 2 KB, detects a URL, and routes to `/recipes/add/share?url=...` instead.

### Flow F — User shares a file type we can't process

1. User shares a `.docx` Word document.
2. Palateful appears (due to `*/*` wildcard fallback).
3. Flutter handler doesn't match any supported type → routes to `/recipes/add/receive?unsupported=true`.
4. Epic 4's receiving screen shows the "we can't read this" graceful fallback with the filename surfaced.

## Frontend changes

### AndroidManifest: expanded intent filters

Current (in `app/android/app/src/main/AndroidManifest.xml`):
```xml
<intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="text/plain" />
</intent-filter>
<intent-filter>
    <action android:name="android.intent.action.SEND" />
    <category android:name="android.intent.category.DEFAULT" />
    <data android:mimeType="text/*" />
</intent-filter>
```

Add filters for:
- `image/*`
- `video/*`
- `audio/*`
- `application/pdf`
- `text/csv`
- `application/vnd.ms-excel`
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `*/*` fallback (advertises Palateful as a target for any file; the Flutter handler decides to accept or route to the unsupported-type screen)

Use separate `<intent-filter>` elements for each MIME type — Android requires this for the sheet to show Palateful consistently across OEMs.

### Runtime permissions (Android 13+)

Add to the manifest:
```xml
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
<uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />
<uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
```

When a shared content URI is received, Flutter must be able to read the bytes. `receive_sharing_intent` plugin handles the URI-to-path conversion, but on Android 13+ we need `READ_MEDIA_*` declared so `ContentResolver.openInputStream(uri)` doesn't hit `SecurityException`. No runtime permission prompt is needed — the permissions are granted implicitly when the user chose Palateful as the share target (the OS grants read access to the shared item via the intent's flags).

### Flutter: content-aware `_handleSharedFiles`

Rewrite `_handleSharedFiles` in `app/lib/main.dart:215-253` to:

1. For each `SharedMediaFile`:
    - Read `file.mimeType` (populated by `receive_sharing_intent` 1.8+ from the intent).
    - Read `file.path` (local FS path or content URI resolved to a temp path by the plugin).
    - Branch priority:
        - If `path` starts with `http://` or `https://` → `/recipes/add/share?url=...`.
        - If `mimeType` matches `text/plain` AND the path points to a file → read first 2 KB; if it contains a URL, extract and route to `/recipes/add/share?url=...`.
        - If `mimeType` matches a supported pattern, route to `/recipes/add/receive?path=...&mime=...`.
        - Otherwise route to `/recipes/add/receive?unsupported=true&filename=...`.
2. Copy the shared file from the temp location to the app sandbox before routing (temp files may be garbage-collected after the 30-second share context). Use `getTemporaryDirectory()` and a UUID-suffixed filename.
3. Keep the existing URL-from-text extraction as a fallback when no MIME type is present.

The routing destination (`/recipes/add/receive`) is Epic 4's new landing screen.

### Flutter: multi-item suppression

If more than one `SharedMediaFile` arrives, process only the first and show a snackbar after navigation: "Only the first item was imported." This matches the locked decision in the PRD (single-file v1; multi-item batch is a follow-up).

## Backend changes

None owned by this epic. Uses Epic 1's presigned upload flow via Epic 4's receiving screen for files.

## Infrastructure changes

None. No new permissions, no manifest entries beyond the app-local manifest.

## Initial design principles

- **Wildcard fallback, narrow handling.** We declare `*/*` so Palateful is a reliable share target for any file, but the Flutter handler quickly shunts unknown types to the graceful-fallback screen. The OS picker user experience is "Palateful is always available," the in-app experience is honest about what we can handle.
- **MIME type is the primary signal; extension is the secondary.** Many Android share sources (especially Google Photos) set MIME correctly. Fall back to extension when MIME is `application/octet-stream` or missing.
- **Inspect content when signals conflict.** A `.txt` with a URL inside is the clearest conflict case — MIME says "text" but content says "URL." Read 2 KB; don't let a single heuristic dominate.
- **Copy immediately, navigate second.** Shared temp files can disappear after the share context exits. Copy to the app sandbox before navigating so the landing screen has a stable path.

## File structure (anticipated)

### Modified
- `app/android/app/src/main/AndroidManifest.xml` — add intent filters + permissions.
- `app/lib/main.dart` — rewrite `_handleSharedFiles`.
- `app/lib/core/router/app_router.dart` — add `/recipes/add/receive` route (contract owned by Epic 4; Android routes there).
- `app/pubspec.yaml` — verify `receive_sharing_intent` version exposes `mimeType` on `SharedMediaFile` (1.8+ does).

## Stories

### Story 1: `sae-1` — AndroidManifest MIME + permission expansion

**AC:**
- Manifest declares separate `<intent-filter>` blocks for `ACTION_SEND` + `ACTION_SEND_MULTIPLE` across: `image/*`, `video/*`, `audio/*`, `application/pdf`, `text/csv`, `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Existing `text/plain`/`text/*` filters preserved. **`*/*` wildcard is NOT declared in v1.**
- Manifest declares `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO` permissions (Android 13+).
- `android:exported="true"` verified on `MainActivity` (already required; regression bullet).
- Play Console Data Safety form updated to disclose `READ_MEDIA_*` and shared-file ingestion; pre-launch report reviewed for new permission warnings before merge.
- Crashlytics tag `share_intent_mime` added to the copy-to-sandbox step so OEM-specific `SecurityException`s surface.
- Manual smoke tests: JPG from Google Photos, PDF from Files, video from WhatsApp — Palateful appears in each.

### Story 2: `sae-2` — Flutter content-aware handler + shared-file copy (+ router params)

**AC:**
- `_handleSharedFiles` `await`s `File.copy()` into `getApplicationDocumentsDirectory()/shared_inbox/<uuid>.<ext>` before calling `_navigateAfterFrame`. Unit test mocks a delete of the source temp file between copy and navigate; route receives the sandbox path successfully.
- `_handleSharedFiles` reads `mimeType` and routes per the MIME → route matrix in the PRD addendum.
- `app_router.dart` accepts `path`, `mime`, `unsupported`, and `filename` query params on `/recipes/add/{photo,pdf,audio,video,spreadsheet,receive}` — this closes the dead-code problem where routes previously ignored shared file paths.
- URL-in-text extraction runs only when (a) MIME is `text/plain` or absent AND (b) shared payload size ≤ 4 KB AND (c) no `SharedMediaFile.path` points to a file on disk. Otherwise the payload is treated as a file share.
- If `AuthService.isAuthenticated` is false when the handler fires, the sandbox path is persisted to `SharedPreferences` under `pending_share_payload` and replayed on first successful auth; covered by widget test.
- `ACTION_SEND_MULTIPLE` with 3 JPGs: navigates on the first item, shows snackbar "Only the first item was imported (2 skipped)", and deletes the skipped sandbox files.
- Unit tests cover the routing matrix, URL-in-text gate, and auth-race replay path.
- Integration test: Android emulator `am start -a ACTION_SEND -t image/jpeg --eu extra.stream file:///...` → expected route reached with sandbox path.

### Story 3: `sae-3` — Unsupported type + graceful fallback wiring

**AC:**
- Sharing a `.docx` routes to `/recipes/add/receive?unsupported=true&filename=cookbook.docx`.
- The receiving screen (owned by Epic 4) handles the `unsupported=true` param with an explanatory message.
- No crashes, no silent drops.
- Device matrix verified via Firebase Test Lab: {Pixel 7 / Android 14, Samsung S23 / OneUI 6, Android 13 reference} × {JPG, PDF, MP4, MP3, `https://…`, `.docx`}. Crashlytics zero new crashes in 24 h post-merge canary.
- Telemetry event `share_intent_unsupported` fires with `{mime, extension, filename}` for the metrics gate that governs future `*/*` unlock.

## Dependencies

- **Blocked by Epic 4 (`epic-share-receiving-ux`)** for the `/recipes/add/receive` route's existence. Can ship `sae-1` (manifest only) and `sae-2` partial (routing logic) in parallel; the unsupported-type flow waits for Epic 4's fallback screen.
- **Not blocked by Epic 1** for the URL and MIME-expansion paths. File-based shares will complete end-to-end only once Epic 1 (backend) + Epic 4 (receiving UX) are live, but the share sheet presence (Android manifest) is fully deliverable standalone.

## Risks surfaced in party-mode (tracked, mitigated in ACs)

- **Content URI permission persistence race:** grants are scoped to the receiving Activity; mitigated by synchronous copy-to-sandbox-before-navigation in `sae-2`.
- **OEM share-sheet quirks** (Samsung / Xiaomi / MIUI cache): mitigated by Firebase Test Lab matrix in `sae-3` + not adding secondary filters that confuse share-target ranking.
- **`*/*` attracting Wear OS / Auto spillover:** avoided by not declaring `*/*` in v1.
- **`ACTION_SEND_MULTIPLE` unreachable without filter:** fixed in `sae-1`.
- **Auth race on cold-start replay:** fixed via `pending_share_payload` in `sae-2`.
- **Play Console sensitive-permission review:** pre-empted in `sae-1`.

## Open questions for the user

None — Android manifest scope is fully specified by the locked "cover everything already supported" decision, and the `*/*` question is resolved (not shipped in v1, metrics-gated).
