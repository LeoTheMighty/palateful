# Story arh-4: HTTPS App Links + assetlinks.json

**Status:** ready-for-dev
**Epic:** epic-android-release-hardening

## Goal

Register `palateful.app` as an Android App Link host so `https://palateful.app/...`
URLs open Palateful directly without the "open with" chooser. The
plumbing is static: an `autoVerify="true"` intent filter in the
manifest plus a `.well-known/assetlinks.json` file served by the
existing Cloudflare Pages web deploy.

The real SHA-256 cert fingerprint only exists after the first manual
AAB upload enrolls us in Play App Signing, so we ship this story with
a placeholder fingerprint + TODO. Until the operator commits the real
fingerprint (per `ANDROID.md` steps 11-12), App Link verification
fails closed and links fall back to the browser chooser — acceptable
for internal-track v1.

## Scope (from epic)

- `AndroidManifest.xml`: add `<intent-filter android:autoVerify="true">`
  under `MainActivity` with `ACTION_VIEW`, `BROWSABLE`, `DEFAULT`,
  `<data android:scheme="https" android:host="palateful.app" />`.
  Preserve the existing `com.palateful.app` custom-scheme filter
  (Auth0 backward-compat).
- `app/web/.well-known/assetlinks.json`: static JSON with
  package_name `com.palateful.palateful`, placeholder
  `sha256_cert_fingerprints` + inline `_comment` describing the
  retrieval procedure.

## Implementation

### `app/android/app/src/main/AndroidManifest.xml`

Append a second `<intent-filter>` alongside the existing Auth0
custom-scheme filter:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https" />
    <data android:host="palateful.app" />
</intent-filter>
```

No HTTP fallback: Auth0 callbacks use `com.palateful.app://`, not
cleartext HTTP.

### `app/web/.well-known/assetlinks.json`

```json
[
  {
    "_comment": "arh-4: ...retrieval procedure (ANDROID.md steps 11-12)...",
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.palateful.palateful",
      "sha256_cert_fingerprints": [
        "FILL-IN-AFTER-PLAY-APP-SIGNING-ENROLLMENT"
      ]
    }
  }
]
```

Flutter's `build web` copies `app/web/**` into `build/web/**` recursively
(dotfile-prefixed dirs included), so the existing Cloudflare Pages
deploy-web workflow picks up `.well-known/assetlinks.json` on the next
deploy. No pipeline change.

## Acceptance criteria (from epic)

- [x] Manifest adds `<intent-filter android:autoVerify="true">` for
  `android:scheme="https"` + `android:host="palateful.app"`.
- [x] `app/web/.well-known/assetlinks.json` exists with placeholder
  fingerprint and inline TODO comment.
- [x] TODO comment references `ANDROID.md` retrieval procedure (Play
  Console → Setup → App Integrity post-first-AAB-upload).
- [ ] Post-first-AAB-upload CI check on `assetlinks.json` availability
  + content-type — owned by `epic-android-ci-hardening` Story 2.
- [ ] Emulator integration test (`am start -W -a VIEW -d https://...`)
  — deferred to QA walkthrough (no emulator in dev harness).
- [x] Auth0 `com.palateful.app://` callback intent filter preserved.

## QA walkthrough

Split into `arh-4-qa-walkthrough.md`.

## File list

### New
- `app/web/.well-known/assetlinks.json`

### Modified
- `app/android/app/src/main/AndroidManifest.xml`
