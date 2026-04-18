# QA walkthrough — sru-1 (universal receiving landing screen)

## Happy paths

- Share an article URL from Safari → Safari share sheet picks Palateful →
  receive screen shows "Importing recipe from allrecipes.com" + progress
  ring → lands on Activity Hub with the new job row highlighted.
- Share a photo from Photos.app → receive screen shows "Reading your
  recipe photo" for ~600 ms → photo capture screen opens with the
  shared image already loaded, uploads, and proceeds through OCR.
- Share a CSV from Files → receive screen shows "Reading your
  spreadsheet" → spreadsheet import screen opens with the file
  pre-filled.
- Share a .txt file with a URL inside from Files → receive screen →
  text-paste screen with the file contents pre-filled; submitting
  calls `/import` with `source_type=text`.

## Deferred flows (sru-4 — upload pipeline)

- PDF, audio, video: receive screen dwells then routes to Activity
  Hub. The presigned-upload PUT is not wired yet; `/import` is not
  called. The Activity Hub will be empty-handed for these branches
  until sru-4 lands. **Don't regression-test these as failures —
  they're intentionally stubbed.**

## Edge cases

- Share an unsupported type (.docx, .zip, .rtf) → unsupported card
  with "Paste Text Instead" action.
- Share a file over 100 MB → oversize card with formatted size
  (e.g. "(118 MB)") and Close action. The upload-url endpoint is
  never called.
- Double-fire: on Android, some OEMs dispatch the share intent
  twice within ~50 ms. The second fire dedups on the
  `sha256(path+mtime+size)` key within a 2 s window.
- URL with no default recipe book: falls through to the existing
  share-import screen (`/recipes/add/share?url=...`) which handles
  the zero-books case.

## Regression checklist

- [ ] Existing URL share flow (`/recipes/add/share`) still works
      from the home screen's "Share" option.
- [ ] Navigator back from the receive card returns to the screen
      that invoked it (not a dead-end home).
- [ ] `sae-2`'s `_handleSharedFiles` snackbar (skippedCount, auth
      replay) still fires — sru-1 doesn't touch that path.
- [ ] Activity Hub still deep-links correctly from the URL share
      success path (`/activity?tab=imports`).

## Known limitations

- The PDF/audio/video branch is a stub until sru-4. Test plans for
  those types must NOT assume the backend gets real bytes — the
  Activity Hub row won't materialise.
- The file-stat-driven tests are documented in `sru-3-qa-walkthrough.md`
  because `flutter_tester`'s fake-async zone stalls `File.stat` in
  initState. Any future "pump-the-share-screen-to-completion"
  widget test needs `tester.runAsync` + real filesystem I/O.
