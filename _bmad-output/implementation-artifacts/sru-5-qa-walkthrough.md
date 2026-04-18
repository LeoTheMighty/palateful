# QA walkthrough — sru-5 (Video file import screen + sheet entry)

## Happy path

- Home screen → Add Recipe → More Options → "Video File" opens
  `/recipes/add/video`. File picker allows `.mp4 .mov .m4v .webm`.
  Choosing a file shows the filename + size; tapping "Upload & Import"
  surfaces the pending-sru-4 error message.

## Edge cases

- File > 100 MB: picker returns, screen shows "File too large —
  max 100 MB" in the error band.
- Cancel from the picker: no state change, no error.
- Unsupported extension: file_picker filters to the allowed list, so
  `.avi` / `.flv` / etc. shouldn't appear.

## Regression checklist

- [ ] The receive screen still routes `video/*` MIME shares through
      the sru-4 upload stub (not the stand-alone video screen).
- [ ] Add Recipe sheet's other options (PDF, Voice Memo, From
      Spreadsheet, Create Manually) still work.
- [ ] Opening the video screen from a recipe-book context passes
      the book id through `extra` and the screen uses it as the
      import target once sru-4 is live.

## Known limitations

- sru-4 isn't live yet, so "Upload & Import" surfaces an explicit
  "coming in the next release" message rather than failing silently.
  Replace this string with the real upload call in sru-4.
