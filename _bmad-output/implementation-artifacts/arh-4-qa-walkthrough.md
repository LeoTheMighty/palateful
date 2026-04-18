# QA walkthrough — arh-4: HTTPS App Links + assetlinks.json

## Smoke prerequisites

- Android emulator with `adb` available (Pixel 7 API 33 or later).
- Cloudflare Pages deploy of `app/web/` has picked up the new
  `.well-known/assetlinks.json`. Verify with `curl`.

## Checklist — static file verification (pre-AAB)

- [ ] `curl -sSI https://palateful.app/.well-known/assetlinks.json`
      returns `200` and `content-type: application/json`.
- [ ] `curl -s https://palateful.app/.well-known/assetlinks.json | jq .`
      parses — confirm the placeholder fingerprint
      (`FILL-IN-AFTER-PLAY-APP-SIGNING-ENROLLMENT`) is still there.
      Once apl-1 runs the first AAB upload, the operator swaps in the
      real SHA-256 from Play Console → Setup → App Integrity → App
      signing key certificate.

## Checklist — emulator (pre-fingerprint)

- [ ] Build a debug APK via `flutter build apk --debug`. Install.
- [ ] `adb shell am start -W -a android.intent.action.VIEW -d
      "https://palateful.app/recipes/r-123"
      com.palateful.palateful`. Confirm the app launches and the
      `app_router` handles `/recipes/r-123`.
- [ ] Without the explicit package argument:
      `adb shell am start -W -a android.intent.action.VIEW -d
      "https://palateful.app/recipes/r-123"` — *before* the real
      fingerprint is committed, the chooser dialog appears (expected:
      autoVerify fails closed).
- [ ] Auth0 login flow still works — launching via a
      `com.palateful.app://...` URL routes into `auth_service.dart`
      unchanged. Sign out, sign back in end-to-end.

## Checklist — emulator (post-fingerprint, owned by epic-android-ci-hardening)

- [ ] After the real SHA-256 is committed into `assetlinks.json` and
      Cloudflare Pages redeploys, run `adb shell pm get-app-links
      com.palateful.palateful` on a fresh install. Look for
      `palateful.app: verified`.
- [ ] `adb shell am start ... "https://palateful.app/..."` without
      the package arg opens Palateful directly — no chooser.

## Regression surface

- Existing `com.palateful.app://` intent filter is preserved, so Auth0
  callbacks remain unchanged.
- No other host (e.g. backend API domain) was added. If you notice
  unrelated links opening Palateful, investigate.

## Out of scope

- Signed-fingerprint CI check (ach-* stories in
  `epic-android-ci-hardening`).
- iOS Universal Links (separate story).
