# QA Walkthrough — sae-2: Flutter content-aware share handler + sandbox copy

Requires an Android device / emulator with the latest APK. Complete
`sae-1` QA first (share sheet surfacing).

## Setup

- [ ] Install the latest APK. Sign in.
- [ ] Keep `adb logcat` open filtering for `palateful` / `Crashlytics`
  breadcrumbs (`adb logcat | grep -i palateful`).

## Sandbox survival

- [ ] Share a JPG from Google Photos. Watch `adb logcat` — you should
  see the app open with the photo screen auto-populated.
- [ ] Delete the original photo from Google Photos immediately after
  sharing. Import still completes successfully (payload was sandboxed
  to `<appDocs>/shared_inbox/`).

## MIME routing matrix

For each row below: trigger the share → confirm Palateful opens on the
expected typed screen with the file pre-selected.

| Source        | MIME                                                           | Expected destination                              |
| ------------- | -------------------------------------------------------------- | ------------------------------------------------- |
| Google Photos | image/jpeg                                                     | `/recipes/add/photo` with the image queued        |
| Files         | application/pdf                                                | `/recipes/add/pdf` with the PDF preselected       |
| Voice Recorder| audio/mpeg                                                     | `/recipes/add/audio` with the MP3 preselected     |
| Drive         | text/csv                                                       | `/recipes/add/spreadsheet` with the CSV preselected|
| Drive         | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | `/recipes/add/spreadsheet` with the XLSX preselected |
| WhatsApp      | video/mp4                                                      | `/recipes/add/receive` unsupported-card fallback (sru-5 lands the video screen) |

- [ ] For each row above, confirmed ✓.

## URL + URL-in-text gate

- [ ] Share a URL from Chrome → routes to `/recipes/add/share`
  (regression).
- [ ] Create a `.txt` file (e.g. via Pulse Files) containing exactly
  `https://allrecipes.com/foo` and share it. Palateful should route to
  `/recipes/add/share?url=https://allrecipes.com/foo` (URL-in-text
  sniff fires).
- [ ] Create a `.txt` file >5 KB containing a URL and share. Palateful
  should NOT auto-extract the URL (gate holds at ≤4 KB).
- [ ] Share plain text without a URL (e.g. "reminder to buy milk") —
  nothing should import; the app should not open the paste screen
  (currently the handler drops silently; sru-1 will surface a
  dedicated "no content to import" state).

## Auth race

- [ ] Log out. Kill the app. From Google Photos, share a JPG to
  Palateful.
- [ ] Palateful cold-launches on the login screen.
- [ ] Log in. The receiving screen should auto-open with the sandboxed
  image pre-selected.
- [ ] `adb shell run-as com.palateful.app cat
  /data/data/com.palateful.app/shared_prefs/*.xml | grep
  pending_share_payload` — key should be absent (consumed + cleared).

## ACTION_SEND_MULTIPLE

- [ ] Open Google Photos, tap Select, pick 3 JPGs, tap Share → choose
  Palateful.
- [ ] App opens on `/recipes/add/photo` with the FIRST photo queued.
- [ ] Snackbar reads: "Only the first item was imported (2 skipped)."
- [ ] `<appDocs>/shared_inbox/` contains exactly one file (the other
  two were skipped without touching disk).

## OEM spot checks

- [ ] Samsung OneUI 6 device: share JPG → works (no SecurityException
  in `adb logcat`).
- [ ] Xiaomi MIUI device: share PDF from Mi Drive → works.
- [ ] If a SecurityException fires during copy-to-sandbox, Crashlytics
  dashboard shows a non-fatal event tagged
  `area=share.intent operation=copyToSandbox share_intent_mime=<mime>
  share_intent_ext=<ext>`.

## Automated regression

- [ ] `flutter test test/core/services/share_intent_handler_test.dart`
  — 16 tests pass.
- [ ] `flutter test
  test/features/recipes/add_recipe/receive_import_screen_test.dart` —
  8 tests pass.
- [ ] `flutter test` (full suite) — 560 tests pass.
