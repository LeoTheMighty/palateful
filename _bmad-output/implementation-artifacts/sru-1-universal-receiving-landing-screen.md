# Story sru-1: Universal receiving landing screen

**Status:** done
**Epic:** epic-share-receiving-ux

## Goal

Replace the sae-3 placeholder at `/recipes/add/receive` with the full
receiving UX: detection → progress card (≥600 ms dwell) → URL import /
typed-screen handoff. Lands the notifier + content-type detection
table + double-fire dedup + error-code map. The PDF / audio / video
presigned-upload body lands in sru-4 (receive screen routes video/*,
application/pdf, and audio/* through an upload shell that currently
bounces straight to the Activity Hub — sru-4 wires real bytes).

## Acceptance criteria

1. `/recipes/add/receive` accepts `url`, `path`, `mime`, `book_id`,
   `unsupported`, `filename` query params. Typed-screen handoff uses
   `go_router.extra` (not query strings — they leak across OS
   processes).
2. URL branch shows "Importing recipe from `<hostname>`", calls the
   existing URL import path, and navigates to `ActivityRoutes.hubPath`.
3. Image / spreadsheet branches delegate to `PhotoCaptureScreen` /
   `SpreadsheetImportScreen` with `initialPath` pre-filled (via
   `go_router.extra`).
4. On mount the screen enters `detecting` state within one frame,
   shows a progress card with type-specific copy, dwells ≥600 ms
   before navigating, and never leaves the card mid-frame.
5. Content-type detection is table-driven (`kMimeToBranch` +
   `kExtensionToBranch`) and regression-tested over the epic's matrix
   (`.jpg .heic .pdf .mp3 .m4a .wav .mp4 .mov .csv .xlsx .txt .docx
   .zip .rtf` + missing-MIME infer-from-extension).
6. First-frame dedup guard: `sha256(path + mtime + size)` — second
   fire within 2 s is a no-op. Same key doubles as the `s3_key`
   suffix in sru-4.
7. Error states keyed on `ReceiveErrorCode`: network, unauthorized,
   tooLarge, objectNotReady, rateLimited, unknown. Each has its own
   copy string; `classifyHttpStatus(code)` maps HTTP to error code.
8. `receive_import_notifier_test.dart` asserts state transitions
   `detecting → uploading → navigating` with monotonic timestamps.

## Implementation

### New
- `app/lib/core/router/activity_routes.dart` — `ActivityRoutes.hubPath`
  single source of truth (`/activity?tab=imports`), insulates the
  share flow from the concurrent `epic-activity-hub-redesign`.
- `app/lib/features/recipes/add_recipe/state/receive_import_notifier.dart`
  — `ReceiveImportNotifier` + `ReceiveImportState` + `ReceiveBranch`
  + `ReceivePhase` + `ReceiveErrorCode` + `detectBranch` +
  `computeDedupKey` + `classifyHttpStatus` + `_DedupGuard` (2 s
  sliding window).
- `app/lib/features/recipes/add_recipe/widgets/receive_progress_card.dart`
  — full-screen progress card with per-branch icon + headline +
  linear progress when uploading.
- `app/test/features/recipes/add_recipe/state/receive_import_notifier_test.dart`
  — 17 tests covering the detection matrix, dedup guard, state
  transitions, and `classifyHttpStatus`.

### Modified
- `app/lib/features/recipes/add_recipe/receive_import_screen.dart` —
  full rewrite. sae-2/sae-3 placeholder body replaced with the sru-1
  UX shell. Preserves the sae-3 `share_intent_unsupported`
  instrumentation.
- `app/lib/core/router/app_router.dart` — receive route now accepts
  `url` + `book_id` params in addition to the existing `path` / `mime`
  / `unsupported` / `filename`. Typed-screen routes read
  `initialPath` / `initialText` from `extra` first, falling back to
  the legacy query-string for deep links in flight.
- `app/lib/features/recipes/add_recipe/widgets/receive_progress_card.dart`
  — exports `formatBytes` for the oversize card (sru-2).
- `app/test/features/recipes/add_recipe/receive_import_screen_test.dart`
  — switched to `dotenv.loadFromString` + `TestWidgetsFlutterBinding`.
  Four tests: unsupported-state render, Paste Text Instead nav,
  Close-to-home, URL progress card.

### Dependencies added
- `crypto: ^3.0.3` in `app/pubspec.yaml` — `sha256` for the dedup
  key. Already transitive; pinning so the import site is explicit.

## Carry-overs

- sru-4 replaces the `_uploadAndImport` stub with the full
  `upload-url` → PUT → `/import` sequence with 409 backoff and
  byte-level progress.
- sru-5 wires the `/recipes/add/video` route + Add Recipe sheet entry.
- The file-I/O driven integration tests (image share → photo screen,
  csv share → spreadsheet screen, txt share → text screen) are
  documented in the QA walkthrough; `flutter_tester` stalls on
  `File.stat` in initState.

## QA walkthrough

See `sru-1-qa-walkthrough.md`.
