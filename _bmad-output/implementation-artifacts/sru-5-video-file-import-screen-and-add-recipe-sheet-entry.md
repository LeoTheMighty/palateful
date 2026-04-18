# Story sru-5: `VideoFileImportScreen` + Add Recipe sheet entry

**Status:** done
**Epic:** epic-share-receiving-ux

## Goal

Surface local-video imports to the user. Two pieces:

1. A stand-alone `VideoFileImportScreen` at `/recipes/add/video`
   that mirrors the shape of `PdfImportScreen` (file picker, size
   cap, submit).
2. A "Video File" row in the Add Recipe sheet's "More Options"
   section that pushes the new route.

The receive screen already routes `video/*` shares via sru-4's
upload sequence (stubbed to land on Activity Hub until sru-4
wires the bytes). This story ships the surface area — the upload
call itself lands in sru-4.

## Acceptance criteria

1. `/recipes/add/video` route live; `VideoFileImportScreen` renders
   a file picker + book ID + 100 MB size gate + "Upload & Import"
   submit.
2. Add Recipe sheet (`add_recipe_sheet.dart`) shows "Video File"
   under More Options with a `videocam` icon and subtitle "Pull a
   recipe from a local video clip".
3. Tapping "Upload & Import" currently surfaces "Video upload is
   coming in the next release" — sru-4 swaps this for the real
   `upload-url` → PUT → `/import` call with `source_type=video_file`.
4. `initialPath` is accepted on the screen so a future share-flow
   delegation works without a follow-up rewrite.

## Implementation

### New

- `app/lib/features/recipes/add_recipe/video_file_import_screen.dart`

### Modified

- `app/lib/core/router/app_router.dart` — registers
  `/recipes/add/video`.
- `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart` —
  adds the "Video File" entry under More Options.

## Carry-overs

- sru-4 replaces the `UnimplementedError` in `_submit` with the
  presigned-upload sequence. The end-to-end ffmpeg → Whisper →
  extraction smoke test lives in Epic 1's `sbf-4`.
- An `initialPath`-integration test (picker-skipped) is documented
  in the manual QA walkthrough — same `flutter_tester` limitation
  as the other typed screens.

## QA walkthrough

See `sru-5-qa-walkthrough.md`.
