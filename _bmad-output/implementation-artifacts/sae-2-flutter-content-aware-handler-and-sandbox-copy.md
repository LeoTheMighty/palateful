# Story sae-2: Flutter content-aware share handler + sandbox copy + router params

**Status:** done
**Epic:** epic-share-android-entrypoint

## Goal

Rewrite `_handleSharedFiles` to be MIME-aware, copy every inbound
payload into a sandbox path before navigating, add `initialPath` query
parameters on typed import screens, register the `/recipes/add/receive`
route (minimal placeholder; sru-1 replaces the body), and replay a
share that arrived before auth rehydrated.

## Scope (from epic)

- `_handleSharedFiles` awaits `File.copy()` into
  `<appDocs>/shared_inbox/<nonce>.<ext>` before navigation so the
  receiving screen never races the OS's temp-file GC.
- Handler reads `SharedMediaFile.mimeType` and routes per the matrix
  in the epic: URL → `/recipes/add/share`, supported file MIME →
  `/recipes/add/receive?path=...&mime=...`, unknown file → `/receive?
  unsupported=true&filename=...`.
- `app_router.dart` accepts `path`, `mime`, `unsupported`, `filename`
  query params on `/recipes/add/{photo,pdf,audio,spreadsheet,receive}`
  — closes the dead-code problem where typed-screen routes previously
  ignored the shared path. (`/recipes/add/video` is sru-5 territory;
  video shares still flow through `/receive`.)
- URL-in-text extraction runs only when MIME is `text/plain` (or
  absent) AND payload / file head is ≤ 4 KB AND the path is NOT a real
  file on disk (prevents hijacking a large clipboard with a URL buried
  in it).
- Auth-race replay: when `AuthService.isAuthenticated` is false at
  classify time, the resolved route is persisted to
  `SharedPreferences` under `pending_share_payload`. A one-shot
  `addListener` callback on `AuthService` consumes + replays the
  payload on the next authenticated notify.
- `ACTION_SEND_MULTIPLE` with N items: only the first is copied to the
  sandbox (skipped items never touch disk). The snackbar surfaces the
  skipped count after navigation.
- Crashlytics tag `share_intent_mime` attached via `ErrorReporter.report`
  if `File.copy()` throws (OEM-specific `SecurityException` forensics).

## Implementation

### New — `app/lib/core/services/share_intent_handler.dart`
Pure classifier with injectable deps (`appDocsDir`, `prefs`,
`authService`, `random`). Produces a `ShareRoute` with a go_router
location + `skippedCount`. Exposes `persistPending` /
`consumePending` for the auth-race replay round trip. Keeps MIME
matching constants (`kSupportedMimePrefixes`, `kSupportedMimeExact`,
etc.) under `@visibleForTesting` so tests can reference them without
the constants leaking into production call sites.

### Modified — `app/lib/main.dart`
`_PalatefulAppState` owns a `ShareIntentHandler` + an `AuthService`
listener. `_handleSharedFiles` calls `handler.resolve`, persists when
unauthenticated, navigates + shows snackbar when authenticated. The
listener is added in `initState` and removed in `dispose` (no
lifecycle leak).

### Modified — `app/lib/core/router/app_router.dart`
- New `/recipes/add/receive` route backed by `ReceiveImportScreen`
  (sae-3). Accepts `path`, `mime`, `unsupported`, `filename` query
  params.
- `/recipes/add/{photo,pdf,audio,spreadsheet}` now each read
  `state.uri.queryParameters['path']` and forward as an `initialPath`
  constructor argument.

### Modified — typed import screens
- `PhotoCaptureScreen`, `PdfImportScreen`, `AudioImportScreen`,
  `SpreadsheetImportScreen` each accept a new optional `initialPath`
  constructor param. When set, `initState` reads the file (or bytes)
  and pre-selects it, skipping the picker. Picker sheet is still
  accessible for the standalone / in-app "Add Recipe" flow. Web is
  guarded (`kIsWeb` skip) so the path is ignored when `dart:io` isn't
  available.

### Modified — `app/pubspec.yaml`
- Added `path_provider: ^2.1.5` (needed for
  `getApplicationDocumentsDirectory` in the handler). Lock updated via
  `flutter pub get`.

## Tests

### New — `test/core/services/share_intent_handler_test.dart`
16 tests covering:
- URL routing (direct `https://` path + URL-in-text inside ≤ 4 KB
  payload + large-payload gate suppression).
- MIME → `/receive` routing for image / pdf / audio / spreadsheet /
  video.
- Missing MIME → extension fallback (`photo.jpg` → `image/jpg`).
- `.docx` → `unsupported=true&filename=...`.
- Sandbox copy survives deletion of the source file.
- `ACTION_SEND_MULTIPLE` with 3 items: first processed, 2 skipped,
  only one file under `<appDocs>/shared_inbox/`.
- `persistPending` + `consumePending` round trip (auth-race replay).
- Empty / degenerate inputs return `null` rather than crashing.

### New — `test/features/recipes/add_recipe/receive_import_screen_test.dart`
(Covered under sae-3 but written in parallel since the route landed in
this story.) 8 widget tests.

## File List

- New: `app/lib/core/services/share_intent_handler.dart`
- New: `app/lib/features/recipes/add_recipe/receive_import_screen.dart`
  (bulk of the behavior is sae-3; route lives here from sae-2 onward)
- New: `app/test/core/services/share_intent_handler_test.dart`
- New: `app/test/features/recipes/add_recipe/receive_import_screen_test.dart`
- Modified: `app/lib/main.dart`
- Modified: `app/lib/core/router/app_router.dart`
- Modified: `app/lib/features/recipes/add_recipe/photo_capture_screen.dart`
- Modified: `app/lib/features/recipes/add_recipe/pdf_import_screen.dart`
- Modified: `app/lib/features/recipes/add_recipe/audio_import_screen.dart`
- Modified: `app/lib/features/recipes/add_recipe/spreadsheet_import_screen.dart`
- Modified: `app/pubspec.yaml`, `app/pubspec.lock`

## QA Checklist

See `sae-2-qa-walkthrough.md` for the standalone walkthrough. Items by AC:

### AC — sandbox copy before navigation
- [ ] Share a JPG from Google Photos → app launches with Palateful's
  receiving screen; the image is pre-loaded in the photo flow.
- [ ] Delete the shared file in Photos mid-import → import still
  completes (payload is already sandboxed).

### AC — MIME matrix
- [ ] JPG → `/recipes/add/receive?mime=image/jpeg` → forwarded to
  `/recipes/add/photo` with the image pre-selected.
- [ ] PDF → receives with `application/pdf` → `/recipes/add/pdf` with
  file pre-selected.
- [ ] MP3 → `/recipes/add/audio` with file pre-selected.
- [ ] CSV → `/recipes/add/spreadsheet` with file pre-selected.
- [ ] MP4 video → receive screen falls back to the "we can't read this"
  state (sru-5 adds the dedicated video flow).

### AC — URL-in-text gate
- [ ] Share a URL from Chrome → `/recipes/add/share?url=...`
  (regression).
- [ ] Share plain text without a URL from Notes → nothing navigates
  (can't import; silently ignored rather than showing paste screen).
- [ ] Share a `.txt` file with a single URL inside → routes to URL
  import.
- [ ] Share a large `.txt` (>4 KB) with a URL inside → does NOT sniff
  the URL (sniff gate holds).

### AC — Auth race replay
- [ ] Kill the app, clear credentials. Share a JPG. App cold-launches
  on the login screen. Sign in. Receiving screen opens with the
  sandbox image pre-loaded.
- [ ] Confirm `SharedPreferences` key `pending_share_payload` is
  cleared after the replay (re-share does not double-fire).

### AC — Multi-item
- [ ] Select 3 JPGs in Google Photos → Share → Palateful. App shows
  photo screen with the first image; snackbar reads "Only the first
  item was imported (2 skipped)."
- [ ] Confirm only one file ended up in `<appDocs>/shared_inbox/`.

### AC — Crashlytics tag
- [ ] Trigger a `SecurityException` by revoking permissions mid-share
  (Samsung simulator). Crashlytics dashboard shows a non-fatal event
  tagged with `share_intent_mime=image/jpeg` + `share_intent_ext=jpg`.
  (Manual on-device — pre-launch-report surface.)
