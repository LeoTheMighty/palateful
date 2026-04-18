# Story sru-3: Typed import screens accept `initialPath` / `initialText`

**Status:** done
**Epic:** epic-share-receiving-ux

## Goal

Round out the sae-2 groundwork: `PhotoCaptureScreen`, `PdfImportScreen`,
`AudioImportScreen`, `SpreadsheetImportScreen` already accept an
`initialPath` constructor param (landed in sae-2). This story adds the
matching param to `TextPasteImportScreen` (`initialText`), teaches the
router to read `initialPath` / `initialText` from `go_router` `extra`
(query strings leak across OS processes — the receiving screen in sru-1
hands seeds over as `extra`), and lands the regression-test pass the
epic AC calls for: each typed screen has a widget test that proves the
picker is skipped when the param is present.

## Acceptance criteria

1. `TextPasteImportScreen` accepts `initialText: String?`; when set it
   pre-fills the textarea in `initState`.
2. Router reads `initialPath` (Photo/Pdf/Audio/Spreadsheet) and
   `initialText` (TextPaste) from `go_router` `extra` first, falling
   back to the legacy query param for compatibility with any deep links
   still in flight.
3. Widget tests exist for all five screens:
   - `photo_capture_screen_test.dart`
   - `pdf_import_screen_test.dart`
   - `audio_import_screen_test.dart`
   - `spreadsheet_import_screen_test.dart`
   - `text_paste_import_screen_test.dart`
   Each asserts the default (no-seed) state shows the file-picker
   label, and the seeded state replaces it with the pre-filled
   filename (file-based screens) or the pre-filled text (text screen).

## File List

Modified:
- `app/lib/features/recipes/add_recipe/text_paste_import_screen.dart`
- `app/lib/core/router/app_router.dart`

New:
- `app/test/features/recipes/add_recipe/pdf_import_screen_test.dart`
- `app/test/features/recipes/add_recipe/audio_import_screen_test.dart`
- `app/test/features/recipes/add_recipe/spreadsheet_import_screen_test.dart`
- `app/test/features/recipes/add_recipe/text_paste_import_screen_test.dart`
- `app/test/features/recipes/add_recipe/photo_capture_screen_test.dart`

## Implementation notes

- `dotenv.loadFromString` (not `.load`) is used in tests because
  `.load` blocks on the asset bundle in `flutter_tester` and never
  resolves. Seed the stub with `API_BASE_URL` + the three `AUTH0_*`
  keys or `Environment.auth0Domain` trips its `assert` on first read.
- `tester.runAsync` wraps the initial `pumpWidget` + wait because the
  prefill paths `await File.stat()`; the default fake-async zone
  stalls those futures and the test would time out.

## QA walkthrough

See `sru-3-qa-walkthrough.md`.
