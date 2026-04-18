# QA walkthrough — sru-3 (typed import screens accept `initialPath` / `initialText`)

## Behaviour under test

- Tapping **Paste Text Instead** on the receive-unsupported card still
  lands on the empty textarea. Good baseline.
- Triggering the share-intent flow with a `.txt` file forwards to
  `/recipes/add/text` with the file contents pre-filled in the
  textarea. Verify the character count reflects the pre-filled
  length.
- On the four file-based screens (photo / pdf / audio / spreadsheet),
  triggering the share flow shows the filename in the picker button
  (or dropzone header) without the OS file picker ever appearing.

## Edge cases

- Non-existent or permission-denied shared path: each screen falls
  back to the file picker label. Check by sharing into Palateful after
  cleaning `<appDocs>/shared_inbox/`.
- Very large files: the per-screen size cap still applies (PDF 50 MB,
  audio 50 MB, spreadsheet 5/10 MB). Seed a too-large file and confirm
  the screen surfaces its size-cap error instead of uploading.
- Legacy query-param deep links: paste
  `palateful://recipes/add/pdf?path=/tmp/foo.pdf` into Safari and
  confirm the path still pre-fills (query-string fallback).

## Regression checklist

- [ ] Opening each typed screen from Add Recipe sheet (no seed) shows
      the default file-picker label.
- [ ] Tapping the picker and choosing a file clears any pre-filled
      seed — the user's picked file wins.
- [ ] After a successful import from a pre-filled seed, the Activity
      Hub shows the new job row.

## Known non-issues

- `tester.runAsync` wrappers in the widget tests — required because
  prefill paths await `File.stat`. Don't "simplify" them back to
  `pump()` calls; the tests will time out.
