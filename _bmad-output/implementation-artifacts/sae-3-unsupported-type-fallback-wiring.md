# Story sae-3: Unsupported type fallback + `/recipes/add/receive` placeholder

**Status:** done
**Epic:** epic-share-android-entrypoint

## Goal

Land a minimal `ReceiveImportScreen` that (a) forwards supported MIMEs
to the typed screen with `?path=` preserved, (b) renders the "we can't
read this yet" fallback card with Paste Text / Close actions when the
share classifier hands it `unsupported=true`, and (c) fires a
`share_intent_unsupported` telemetry breadcrumb that the metrics gate
for future `*/*`-wildcard unlock will eventually watch.

This is explicitly a placeholder implementation — `sru-1`
(epic-share-receiving-ux) replaces the body with the full progress
card + byte-level upload UX + dedup guard. Keep the route and query
param contract stable so swapping in `sru-1` is a body-only change.

## Scope (from epic)

- `?unsupported=true&filename=cookbook.docx` renders a two-button card
  with "Paste Text Instead" (→ `/recipes/add/text`) and "Close"
  (→ `/`).
- Supported MIME hint + `?path=` forwards to the typed screen.
  (`image/*` → `/photo`, `application/pdf` → `/pdf`, `audio/*` →
  `/audio`, spreadsheet MIMEs → `/spreadsheet`.)
- Unrecognized MIME (e.g. `application/octet-stream`) or any case the
  handler can't classify (including `video/*` until `sru-5`) falls
  back to the "we can't read this" card instead of silently dropping.
- Telemetry: `ErrorReporter.log('share_intent_unsupported mime=<m>
  ext=<e> filename=<f>')` on mount when `unsupported=true`.

## Implementation

### New — `app/lib/features/recipes/add_recipe/receive_import_screen.dart`
- Accepts `path`, `mime`, `unsupported`, `filename` via constructor.
- In `initState`: if `unsupported`, fire the telemetry breadcrumb; else
  schedule a post-frame callback that calls `context.go(<typed
  route>)` with the preserved `path`. If no typed route matches, flip
  a local `_fallbackToUnsupported` flag and render the unsupported
  card — the user never gets stuck on a spinner.
- Route mapping table in `_routeByMime`: straight MIME branches + fall
  through.

### Modified — `app/lib/core/router/app_router.dart`
Route registered in sae-2; no new route in sae-3 itself. The screen
import lands here.

## Tests

### New — `test/features/recipes/add_recipe/receive_import_screen_test.dart`
8 widget tests:
- `unsupported=true` renders copy with the filename surfaced + both
  action buttons.
- "Paste Text Instead" navigates to `/recipes/add/text`.
- `image/jpeg` + `?path=` → stub `/recipes/add/photo` screen with the
  path echoed through.
- `application/pdf` → `/recipes/add/pdf` forwarding.
- `audio/mpeg` → `/recipes/add/audio` forwarding.
- `text/csv` → `/recipes/add/spreadsheet` forwarding.
- `application/octet-stream` → unsupported card fallback.
- `video/mp4` → unsupported card fallback (no typed screen yet).

## File List

- New: `app/lib/features/recipes/add_recipe/receive_import_screen.dart`
- New: `app/test/features/recipes/add_recipe/receive_import_screen_test.dart`
- Updated: `app/lib/core/router/app_router.dart` (import only; route
  itself landed in sae-2)

## QA Checklist

See `sae-3-qa-walkthrough.md` for the standalone walkthrough.

### AC — Unsupported routing
- [ ] Share a `.docx` (once `*/*` is eventually enabled — otherwise
  simulate via `am start -a android.intent.action.SEND
  -t application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
  → receive screen shows "We can't read this yet" with the filename
  rendered in a monospace font.
- [ ] Tap "Paste Text Instead" → `/recipes/add/text`.
- [ ] Tap "Close" → home screen.

### AC — MIME forwarding
- [ ] Share a JPG → `/recipes/add/photo` opens with the image queued
  (no detour card).
- [ ] Share a PDF → `/recipes/add/pdf` opens pre-selected.
- [ ] Share an MP3 → `/recipes/add/audio` opens pre-selected.
- [ ] Share a CSV → `/recipes/add/spreadsheet` opens pre-selected.

### AC — Fallback safety
- [ ] Share a video file → receive screen shows unsupported card
  rather than a stuck spinner (sru-5 will land the dedicated video
  screen).

### AC — Telemetry
- [ ] Trigger an unsupported share. `adb logcat | grep
  share_intent_unsupported` shows one line per unsupported share with
  `mime=...`, `ext=...`, `filename=...` captured.
- [ ] Firebase Test Lab / Crashlytics non-fatal log entries are the
  on-device surface (debug-only via `debugPrint` otherwise).

### AC — Device matrix (pre-canary)
- [ ] Pixel 7 / Android 14 — all six file types above behave as
  expected.
- [ ] Samsung S23 / OneUI 6 — repeat.
- [ ] Android 13 reference device — repeat.
- [ ] Post-canary Crashlytics non-fatal rate does not increase 24 h
  after the merge (empirical check — not automatable).
