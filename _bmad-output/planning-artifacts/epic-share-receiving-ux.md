<!-- refined via party-mode 2026-04-18 -->
# Epic: Universal Receiving UX — one landing screen for every shared file

## Locked cross-epic decisions (inherited — do not re-litigate)

1. **Single upload contract** — receiving screen uses `upload-url` → PUT → `/import {s3_key, etag}` with 3× 500 ms backoff on 409 `object_not_ready`. Owned by Epic 1.
2. **Sandbox-first rule** — the screen only ever receives sandbox paths (from Android `_handleSharedFiles` copy + iOS App Group security-scoped copy). Never content URIs, never OS temp paths.
3. **Machine-readable error codes** — each 4xx maps to a distinct copy string, not a string-parsed message.

## Added by this workshop

- **Delegation principle clarified.** Typed screens with non-picker UI (photo has camera/preview; spreadsheet parses rows client-side with a column picker) get the file pre-filled and handle the upload themselves. Pure-upload types (PDF / audio / video) stay on the receiving screen through to Activity Hub. This isn't "mature vs. new" — it's "has UI beyond a picker" vs. "doesn't."
- **Activity Hub route is a single constant** (`ActivityRoutes.hubPath`). Insulates this epic from the concurrent `epic-activity-hub-redesign`.
- **Double-fire guard.** Receiving notifier guards on first-frame against OS duplicate intent fire; dedup key is `sha256(path+mtime+size)` used as the s3_key suffix so a second PUT to the same key is a no-op.
- **Minimum dwell on the receiving card** (600 ms) — avoids a visual glitch when a fast URL dispatch would otherwise flash-and-replace.

## Overview

Today when `_handleSharedFiles` in `app/lib/main.dart` routes a shared file to `/recipes/add/pdf` or `/recipes/add/audio`, the destination screen opens its own file picker — the shared file path is dropped on the floor because those screens have no constructor param for a pre-selected file. Users who got this far would see a file picker asking them to pick the file they just shared. That's the silent handoff gap.

This epic adds a new universal `/recipes/add/receive` landing screen that handles content-type detection, shows a two-second progress context, and routes to the appropriate typed import screen with the file path pre-filled. Every typed import screen (`photo`, `pdf`, `audio`, `spreadsheet`, new `video_file`) is updated to accept an optional pre-selected file path and skip its own picker. A graceful "we can't read this" fallback screen covers unsupported types.

## Goal

Any shared file, URL, or text from either platform lands on a single receiving screen that detects the content type, uploads (for files), and threads the user either to the typed import flow or to the Activity Hub where the job is already running. Unsupported types get a single clear message with a path forward.

## End-user flow

### Flow A — Shared URL (Safari / Chrome)

1. User shares a URL. Extension (iOS) or main-app intent (Android) fires.
2. Landing screen `/recipes/add/receive?url=https://...` loads.
3. Screen shows a full-screen card: website-icon + "Importing recipe from allrecipes.com" + progress ring (≤1 second).
4. Screen dispatches the URL import API call (or delegates to `share_import_screen.dart` — see design).
5. Screen navigates to the Activity Hub with the new job row highlighted.

### Flow B — Shared photo

1. User shares a photo. Landing screen `/recipes/add/receive?path=/tmp/x.jpg&mime=image/jpeg` loads.
2. Screen shows: photo-thumbnail + "Reading your recipe photo" + progress ring.
3. Auto-detects it's an image; navigates to the existing photo import flow with the file pre-selected (skipping the camera / file-picker sheet).
4. User sees the existing on-device OCR + review flow.

### Flow C — Shared PDF

1. Landing screen loads with PDF MIME.
2. Screen shows: PDF icon + "Reading your PDF" + progress ring.
3. PDF is small (<100 MB) — uploads via `/v1/imports/upload-url` presigned PUT, then calls `/import` with `s3_key` and `source_type="pdf"`.
4. Navigates to Activity Hub; backend handles the multi-recipe boundary detection + review flow per existing PDF path.

### Flow D — Shared audio

1. Landing screen loads with audio MIME.
2. Screen shows: audio icon + "Transcribing audio…" + progress ring.
3. Uploads via presigned PUT, calls `/import` with `source_type="audio"` + `s3_key`.
4. Navigates to Activity Hub.

### Flow E — Shared video file (local clip)

1. Landing screen loads with `video/*` MIME.
2. Screen shows: video-thumbnail + "Extracting recipe from video" + progress ring.
3. Uploads via presigned PUT, calls `/import` with new `source_type="video_file"` + `s3_key`.
4. Navigates to Activity Hub. Backend ffmpeg → audio → Whisper → text extraction runs in the worker.

### Flow F — Shared spreadsheet

1. Landing screen loads with CSV / XLSX MIME.
2. Screen shows: spreadsheet icon + "Reading your spreadsheet".
3. Auto-routes to the existing spreadsheet import screen with the file pre-selected (it parses rows locally before calling `/import` with URL list or structured data).

### Flow G — Unsupported file type (.docx, .zip, etc.)

1. Landing screen loads with `?unsupported=true&filename=notes.docx`.
2. Screen shows: grayed file icon + "We can't read this yet" + "Palateful can't extract recipes from `notes.docx`. Try copying the text and using **Paste Text** instead."
3. Two buttons: **Paste Text Instead** (routes to `/recipes/add/text`) and **Close** (back to home).
4. No crash, no API call, no failed ImportJob.

### Flow H — Too-large file (Android side; iOS catches before this screen)

1. Android side didn't catch oversize; landing screen gets `?path=/tmp/huge.mp4` and reads size.
2. Shows: "That file is too large (410 MB, max 100 MB). Try trimming it or using a cloud link instead."
3. **Close** button returns to the home screen.

## Frontend changes

### New screen: `/recipes/add/receive`

- Path: `app/lib/features/recipes/add_recipe/receive_import_screen.dart`.
- Full-screen; hides app chrome; designed for a short handoff window (≤2s).
- Accepts query params:
    - `url: String?` — direct URL import
    - `path: String?` — local file path (iOS or Android sandbox)
    - `mime: String?` — MIME type hint from the share intent
    - `unsupported: bool` — render the "we can't read this" state
    - `filename: String?` — shown in unsupported state
    - `book_id: String?` — pre-selected recipe book (from iOS extension's book picker)
- Content-type detection:
    1. If `url` present → URL branch.
    2. If `path` present → read `mime` param; if missing, infer from extension.
    3. If both missing or `unsupported=true` → unsupported state.
- Size check: before uploading a file, `File(path).lengthSync()`; if >100 MB, show the too-large state.
- Routing logic after detection:
    - URL → direct import API call → Activity Hub.
    - Image → delegate to `PhotoCaptureScreen(initialPath: path)` — new constructor param, skip picker.
    - PDF → upload + import API call with `source_type="pdf"` → Activity Hub.
    - Audio → upload + import API call with `source_type="audio"` → Activity Hub.
    - Video → upload + import API call with `source_type="video_file"` → Activity Hub.
    - Spreadsheet → delegate to `SpreadsheetImportScreen(initialPath: path)` — new constructor param, skip picker.
    - Text file with URL inside → treat as URL.
    - Text file without URL → delegate to `TextPasteImportScreen(initialText: content)`.
    - Unknown → unsupported state.

### Modified typed import screens

All four existing screens + the new video screen accept a pre-selected path / text:

- `PhotoCaptureScreen`: add `initialPath: String?` param; if set, skip picker and jump straight to confirmation with the file loaded.
- `PdfImportScreen`: add `initialPath: String?` param; if set, skip `FilePicker`, stream the file via the upload flow.
- `AudioImportScreen`: add `initialPath: String?` param; if set, skip `FilePicker`.
- `SpreadsheetImportScreen`: add `initialPath: String?` param; if set, skip `FilePicker`.
- `TextPasteImportScreen`: add `initialText: String?` param; if set, pre-fill the textarea.

Each screen stays fully functional in its existing "user navigated from Add Recipe sheet" flow. The param is optional and additive.

### New screen: `VideoFileImportScreen`

- Path: `app/lib/features/recipes/add_recipe/video_file_import_screen.dart`.
- Minimal: file picker (when launched standalone), upload progress, book picker, submit.
- Matches the shape of `PdfImportScreen` — essentially the same form with a different MIME pattern.
- Routed via `/recipes/add/video` in `app_router.dart`.

### Progress and confirmation UI

- The receiving screen animates through discrete stages: "Receiving…" (≤200 ms) → "Uploading… 40%" → "Sending to Palateful…" → "✓" flash → dispatch to destination.
- If uploading takes >5 s (large PDF or video), keep the progress bar visible; the user sees steady progress and knows the app isn't stuck.
- No progress if the destination is a typed screen (e.g., photo) — just hand off immediately.

### Error states

- Network error during upload: "Couldn't upload. Try again." with Retry + Close.
- 413 from upload-url endpoint: "Too large" message as in Flow H.
- 401: "Your session expired. Sign in again to import." with Close.
- Any other 4xx/5xx: generic "Something went wrong. Please try again." + Close.

## Backend changes

None owned by this epic. Depends on Epic 1 for the upload + import endpoints.

## Infrastructure changes

None.

## Initial design principles

- **One landing screen, many exits.** Every share — iOS or Android — goes through `/recipes/add/receive`. It's the single place to evolve detection logic, tracking, and error handling.
- **Show progress, never stall silently.** Even a 400 ms progress ring is better than a black screen. Large uploads get a live byte counter.
- **Delegate to existing screens when they're the right home.** Photos and spreadsheets have mature screens — the receiving flow just pre-fills the path and navigates. Only the "pure upload → activity hub" path (URL, PDF, audio, video) stays on the receiving screen.
- **Honest about what we can do.** Unsupported types get a single clear message with a one-tap escape hatch (Paste Text Instead). Never a failed job in the Activity Hub.
- **Safe for double-fire.** If the user somehow re-triggers the share handoff mid-upload (OS edge case), the second invocation dedups on a nonce in the extension's `s3_key`.

## File structure (anticipated)

### New
- `app/lib/features/recipes/add_recipe/receive_import_screen.dart`
- `app/lib/features/recipes/add_recipe/video_file_import_screen.dart`
- `app/lib/features/recipes/add_recipe/widgets/receive_progress_card.dart`
- `app/lib/features/recipes/add_recipe/widgets/unsupported_share_card.dart`
- `app/lib/features/recipes/add_recipe/state/receive_import_notifier.dart`

### Modified
- `app/lib/core/router/app_router.dart` — add `/recipes/add/receive`, `/recipes/add/video`.
- `app/lib/features/recipes/add_recipe/photo_capture_screen.dart` — `initialPath` param.
- `app/lib/features/recipes/add_recipe/pdf_import_screen.dart` — `initialPath` param.
- `app/lib/features/recipes/add_recipe/audio_import_screen.dart` — `initialPath` param.
- `app/lib/features/recipes/add_recipe/spreadsheet_import_screen.dart` — `initialPath` param.
- `app/lib/features/recipes/add_recipe/text_paste_import_screen.dart` — `initialText` param.
- `app/lib/main.dart` — update `_handleSharedFiles` routing targets (overlap with Epic 3 `sae-2`; coordinate merge).
- `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart` — add "Video file" as a new item under More Options.

## Stories

### Story 1: `sru-1` — Universal receiving landing screen (URL + typed handoff)

**AC:**
- `/recipes/add/receive` route registered; accepts `url`, `path`, `mime`, `book_id`, `unsupported`, `filename` query params. `initialPath` on typed screens passed via `go_router` `extra` (not query string — query strings leak across OS processes).
- URL branch: loads, shows "Importing recipe from <hostname>", calls existing URL import path, navigates to `ActivityRoutes.hubPath`.
- Image / spreadsheet branches: delegate to the existing typed screen with `initialPath` pre-filled (depends on `sru-3`).
- On mount the screen enters `detecting` state within 16 ms (one frame), shows the progress card with type-specific copy per the Flow table, dwells for ≥600 ms, and never navigates away before the card has rendered at least one full frame.
- Content-type detection is **table-driven** (regression-test over `.jpg .heic .pdf .mp3 .m4a .wav .mp4 .mov .csv .xlsx .txt .docx .zip .rtf` + missing-MIME-infer-from-extension).
- First-frame dedup guard: receiving notifier ignores the second fire of an identical `(path, mtime, size)` within 2 s (OS double-fire).
- Error states: network error, 401, 413, 409, generic — all keyed on `error_code` and showing Close/Retry.
- `receive_import_notifier_test.dart` asserts state transitions `detecting → uploading → navigating` with monotonic timestamps.

### Story 2: `sru-2` — Unsupported type + oversize screen

**AC:**
- `?unsupported=true&filename=...` renders the "We can't read this yet" state with a Paste Text Instead action.
- Before any upload-url request, screen calls `File(path).length()` (async). If ≥ 100 × 1024 × 1024 bytes OR stat fails, renders the too-large state with actual size formatted via `formatBytes`. **No upload-url call is made; test asserts zero network activity in this branch.**
- Both states have a Close button that returns home.
- Screenshot tests for both states.

### Story 3: `sru-3` — Typed import screens accept `initialPath` / `initialText`

**AC:**
- `PhotoCaptureScreen`, `PdfImportScreen`, `AudioImportScreen`, `SpreadsheetImportScreen` each accept a new optional `final` constructor param `initialPath: String?` and skip their file pickers when provided.
- `TextPasteImportScreen` accepts `initialText: String?` and pre-fills the textarea.
- Existing tests in `app/test/features/recipes/add_recipe/photo_capture_screen_test.dart`, `pdf_import_screen_test.dart`, `audio_import_screen_test.dart`, `spreadsheet_import_screen_test.dart`, `text_paste_import_screen_test.dart` still pass unchanged.
- Each screen has a new test that asserts the picker is skipped when the param is present.

### Story 4: `sru-4` — Presigned upload path for PDF / audio / video (in-screen)

**AC:**
- Sequence: request `upload-url` → PUT file to S3 (capture `ETag` header) → POST `/import` with `{s3_key, etag, source_type, book_id}`. On `201` navigate to Activity Hub; on `409 object_not_ready` retry `/import` up to 3× with 500 ms backoff before surfacing error.
- Byte-level progress rendered on the receiving screen during PUT. Progress card covers the full "copy-to-sandbox → uploading → sending" sequence — never black-screen.
- Screen holds an `HttpClient` that `abort()`s when the screen disposes (user tapped Close or Android back); this prevents half-uploaded S3 objects (lifecycle rule in Epic 1 sweeps them at 24 h as a backstop).
- Integration test mocks upload-url, S3 PUT, `/import` and asserts the `{s3_key, etag}` body shape + 409-retry path.

### Story 5: `sru-5` — New `VideoFileImportScreen` + Add Recipe sheet entry

**AC:**
- `/recipes/add/video` route live; standalone `VideoFileImportScreen` renders a file picker and submits a `video_file` import via `sru-4`'s upload sequence.
- Receiving screen routes MIME `video/*` directly via `sru-4` (no intermediate stop on the video screen in the share flow).
- Add Recipe sheet (`add_recipe_sheet.dart`) shows "Video file" under More Options, launching `/recipes/add/video`.
- Integration test: `video_file_import_screen_test.dart` mocks file picker, `upload-url`, S3 PUT, and `/import`; asserts `source_type="video_file"` and the navigation target. (End-to-end ffmpeg smoke test lives in Epic 1's `sbf-4`.)

## Dependencies

- **Blocked by Epic 1 (backend)** — upload endpoints and `s3_key` / `video_file` support.
- **Blocked by Epic 3 partially** — Android hands off to this receiving screen. Epic 3 stories `sae-2` and `sae-3` end here.
- **Unblocks Epic 2** — iOS extension points users here on the main-app side after push notification (deep link in the push payload lands on `/activity` per the architecture addendum, but Epic 4 is where the main-app handoff surface lives for Android + any iOS re-handoff from App Group state).

## Risks surfaced in party-mode (tracked, mitigated in ACs)

- **Activity Hub route shift** during `epic-activity-hub-redesign`: mitigated by `ActivityRoutes.hubPath` single source of truth.
- **201-before-S3-flush race:** mitigated by `HeadObject` in Epic 1 + `409` retry handshake in `sru-4`.
- **Close-mid-upload leaks:** mitigated by `HttpClient.abort()` on dispose + Epic 1's 24 h lifecycle backstop.
- **iOS App Group security-scoped access:** mitigated by security-scoped copy-to-sandbox before the receiving screen sees the path (handled by Epic 2's extension or its main-app handoff).
- **Android `content://` URI vs. path model:** mitigated by Epic 3's sandbox-copy rule — receiving screen only ever sees the sandbox path.
- **OS double-fire of deep-link intent:** mitigated by first-frame dedup guard in `sru-1`.
- **Dead visual transitions:** mitigated by 600 ms minimum dwell in `sru-1`.

## Open questions for the user

None. The receiving screen behavior is fully specified by the locked scope decision + existing Activity Hub / Add Recipe sheet conventions.
