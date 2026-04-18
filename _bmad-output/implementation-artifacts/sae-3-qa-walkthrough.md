# QA Walkthrough — sae-3: Unsupported type fallback + /recipes/add/receive placeholder

This walkthrough exercises the receive screen in isolation. Complete
`sae-1` and `sae-2` QA first — they validate the share sheet + handler
stack that feeds this screen.

## Setup

- [ ] Install the latest APK. Sign in + complete onboarding.
- [ ] Enable `adb logcat | grep -i palateful` to watch for the
  `share_intent_unsupported` breadcrumb.

## Unsupported-type copy

- [ ] Simulate a `.docx` share (either via `am start -a
  android.intent.action.SEND -t
  application/vnd.openxmlformats-officedocument.wordprocessingml.document
  --es android.intent.extra.TEXT notes` — or wait until the `*/*`
  wildcard is unlocked on a future release).
- [ ] Confirm the receive screen shows:
  - Title: "We can't read this yet"
  - Body copy mentions the shared filename (e.g. ``notes.docx``)
  - Two buttons: **Paste Text Instead** and **Close**
- [ ] Tap **Paste Text Instead** → navigates to `/recipes/add/text`.
- [ ] Kill the app and repeat; tap **Close** → lands on home.

## MIME forwarding

Complete the cases below. The receive screen should be visually
indistinguishable from routing straight to the typed screen — a
single progress spinner appears only briefly before the typed screen
replaces it.

- [ ] `image/jpeg` share → `/recipes/add/photo` with image queued.
- [ ] `application/pdf` share → `/recipes/add/pdf` pre-selected.
- [ ] `audio/mpeg` share → `/recipes/add/audio` pre-selected.
- [ ] `text/csv` share → `/recipes/add/spreadsheet` pre-selected.
- [ ] `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  share → `/recipes/add/spreadsheet` pre-selected.

## Fallback safety (never stuck on spinner)

- [ ] Share a video file (`video/mp4`) → receive screen falls through
  to "We can't read this yet" (sru-5 owns the dedicated video screen).
- [ ] Manually craft a share with
  `application/octet-stream` MIME → same fallback card. (Not a common
  share; mostly tests the unrouted-MIME defensive path.)

## Telemetry

- [ ] After triggering an unsupported share, `adb logcat` should
  contain a line like:
  `I/flutter ( 1234): [ErrorReporter.log] share_intent_unsupported
   mime=application/... ext=docx filename=notes.docx`
- [ ] In release builds, the same breadcrumb is attached to
  Crashlytics — check the next non-fatal event in the Firebase
  console.

## Automated regression

- [ ] `flutter test
  test/features/recipes/add_recipe/receive_import_screen_test.dart`
  → 8 tests pass.
- [ ] `flutter test` (full suite) → all tests pass.

## Known limitations (scoped to sru-1)

- No byte-level progress card during the MIME-forwarding delay. The
  placeholder shows a plain `CircularProgressIndicator`.
- No 600 ms minimum dwell. Forwarding is as fast as the navigation
  can complete.
- No dedup guard on double-fire of `getInitialMedia()`. The handler
  doesn't today produce duplicates in practice, but sru-1 will add the
  `(path, mtime, size)` hash check before shipping presigned upload.

These land with `sru-1` in `epic-share-receiving-ux`.
