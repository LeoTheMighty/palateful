<!-- refined via party-mode 2026-04-18 -->
# Epic: Android Release Hardening

## Locked cross-epic decisions (inherited — do not re-litigate)

1. **Contact email v1 is `leonid@ac93.org`** (from `epic-android-privacy-policy-page` workshop). Applies anywhere the app or ANDROID.md needs a user-facing support address.
2. **Privacy policy ships FIRST** at `https://palateful.app/privacy`. This epic can proceed in parallel but cannot ship before the page is live.

## Added by this workshop

- **Adaptive icon via `flutter_launcher_icons` package**, not hand-authored XML. One source PNG (`app/android/play-store-assets/icon-source-1024.png`, 1024×1024, transparent) drives every density variant + adaptive foreground/background + Android-13+ monochrome. Re-runs as a Dart build step: `dart run flutter_launcher_icons`. Same source PNG is down-scaled by `epic-android-play-console-launch` Story `apl-2` for the 512×512 Play Store icon. One source of truth, zero manual density-ladder math.
- **`assetlinks.json` ships with placeholder SHA-256 + TODO**. The real fingerprint only exists after the first manual AAB upload enrolls us in Play App Signing (owned by `apl-1` → Play Console → Setup → App Integrity → App signing key certificate → copy SHA-256). ANDROID.md step 11–12 is the handoff: operator commits the real fingerprint back into `app/web/.well-known/assetlinks.json`, Cloudflare Pages deploys it on next merge. Until that commit lands, App Links *don't verify* and links fall back to the browser chooser — acceptable for internal-track v1.
- **POST_NOTIFICATIONS smoke on Android 13+ emulator is mandatory pre-first-tag**, since we have no device. `ANDROID.md` step 17 includes the exact `adb shell` command to simulate an FCM delivery on a fresh Pixel 7 API 34 emulator and observe the notification in the shade. If this fails, no tag push.
- **No double-prompt risk**: the existing onboarding notification-permission screen (`app/lib/features/onboarding/onboarding_notification_permission_screen.dart`) already calls `firebase_messaging.requestPermission()`, which on Android 13+ (once `POST_NOTIFICATIONS` is declared) triggers the native OS prompt. No separate Android code path. Story `arh-1` *verifies* this routing, doesn't add a parallel Android prompt.
- **Notification channel created eagerly at app init**, not on first push. Store id `palateful_default`, name "Palateful Notifications", importance HIGH. FCM payloads coming from the API must declare matching `android.notification.channel_id`. Backend push config was already checked — no backend change.
- **Cleartext `http://palateful.app` is NOT declared** — HTTPS-only App Links. Auth0 custom-scheme callback (`com.palateful.app://`) is preserved for backward-compat; App Links are additive, not replacing.
- **Single GCP service account for CI** (propagates forward to `epic-android-ci-hardening`): one JSON that has Play Console release-manager + Firebase Crashlytics upload + Firebase Test Lab roles. Simpler secret rotation; `ANDROID.md` Section 6 documents the role list.

## Overview

The Android app builds today, but several gaps prevent a clean Play Store internal-track release:

- **FCM notifications silently fail on Android 13+** because `POST_NOTIFICATIONS` isn't declared and no runtime prompt exists.
- **Launcher icon is raster-only** — no adaptive icon XML (foreground + background + monochrome), so Pixel devices render it inside a dumb square.
- **No 512×512 Play Store icon asset** lives in the repo. Play Console requires it at listing time.
- **`READ_MEDIA_IMAGES/VIDEO/AUDIO` were over-declared in `sae-1`** — the Jan 2025 Play policy tightened these to apps that genuinely browse the user's media library. Shared-file intents already grant temporary read via `FLAG_GRANT_READ_URI_PERMISSION`; declaring the permissions now invites review friction with no benefit.
- **No Android App Links** — `com.palateful.app://` custom scheme works for Auth0 but `https://palateful.app/...` links open in a browser chooser instead of the app. Missing `.well-known/assetlinks.json` on palateful.app.
- **Crashlytics native symbols aren't uploaded** — release crashes from native libs (Flutter engine, Firebase SDK) will surface unsymbolicated.

The fixes are small and local. Operator has no Android device, so validation leans on Play Console's Pre-Launch Report + Firebase Test Lab soft-smoke in CI (wired by `epic-android-ci-hardening`) + internal-track tester installs.

## Goal

An AAB that passes Play Console review without sensitive-permission friction, delivers FCM notifications on Android 13+, opens `https://palateful.app/...` links directly, and produces symbolicated Crashlytics reports — all without an Android device in the loop.

## End-user flow

### Flow A — User installs from Play Store internal track on a Pixel 8 running Android 14

1. User taps the internal-track opt-in URL from an email invite.
2. Google Play opens and shows Palateful's listing.
3. User taps "Install". App downloads and installs.
4. User taps the app icon — a clean **adaptive icon** (monochrome for themed icons, foreground + background for everything else) appears on the home screen, not a raster square in a boxed container.
5. User opens the app. Onboarding flow runs.
6. At the notification-permission step (already in onboarding), a native Android 13+ prompt asks "Allow notifications?" — *today* this prompt never appears because `POST_NOTIFICATIONS` isn't declared; *after this epic* it does.
7. User grants permission. Later, when an import completes server-side and FCM delivers a message, the notification actually shows in the shade.

### Flow B — User clicks a shared palateful.app/recipes/abc URL from an SMS

1. Friend texts a link: `https://palateful.app/recipes/r-123`.
2. User taps.
3. Android sees `palateful.app` is an App-Link-verified host (per `.well-known/assetlinks.json` served by our web deploy) → opens Palateful directly, bypassing the "open with" chooser.
4. App receives the deep link via existing `go_router` + share-intent handling.

### Flow C — User shares a photo from Google Photos (post-hardening)

1. User long-presses a photo, taps Share → Palateful.
2. Palateful receives the intent. **It does not need `READ_MEDIA_IMAGES`** — the intent carries `FLAG_GRANT_READ_URI_PERMISSION` and `ContentResolver.openInputStream(uri)` succeeds without the manifest permission.
3. Share handler (already built in sae-2) copies to the sandbox and routes to the import screen.

### Flow D — App crashes in release mode on a tester's phone

1. App crashes (e.g., a native-side Flutter engine assert).
2. Firebase Crashlytics captures the crash + native stack trace.
3. In the Firebase console, the stack frames are **symbolicated** — method names, file paths, line numbers visible — because the Fastlane build uploaded NDK symbols at AAB publish time.

## Frontend changes

### AndroidManifest.xml (`app/android/app/src/main/AndroidManifest.xml`)

**Add:**
- `<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />` at the top with the other permissions.
- A new `<intent-filter android:autoVerify="true">` under `MainActivity` declaring `ACTION_VIEW` + `BROWSABLE` + `<data android:scheme="https" android:host="palateful.app" />`. Keeps `ACTION_VIEW` + `com.palateful.app` custom scheme intact for Auth0 backward-compat.
- A second `<intent-filter>` for `http://palateful.app` (cleartext) → no, leave it `https`-only; Auth0 uses the custom scheme.

**Remove:**
- `<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />`
- `<uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />`
- `<uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />`

**Comment update:** the `sae-1` comment above the share intent filters (currently lines 55–58) loses its "runtime permissions for Android 13+" reference. Update inline to note the removal + reasoning (Jan 2025 Play policy; intent-grant flag suffices).

### Launcher icons (via `flutter_launcher_icons`)

- Add `flutter_launcher_icons` to `dev_dependencies` in `pubspec.yaml`.
- Configure under `flutter_launcher_icons:` key with `android: true`, `image_path: app/android/play-store-assets/icon-source-1024.png`, `adaptive_icon_foreground: <same>`, `adaptive_icon_background: "#<cream hex from brand palette>"`, `min_sdk_android: 26`, and `image_path_android_monochrome: <monochrome source>`.
- Run `dart run flutter_launcher_icons`. It generates:
  - `app/android/app/src/main/res/mipmap-{hdpi,xhdpi,xxhdpi,xxxhdpi,mdpi}/ic_launcher.png` (raster; overwrites existing).
  - `app/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` (adaptive icon + monochrome).
  - `app/android/app/src/main/res/drawable/ic_launcher_foreground.xml` + `values/ic_launcher_background.xml`.
- Generated files are committed to git (same pattern as existing mipmap PNGs).
- Existing pre-API-26 raster fallback preserved by the plugin's output.

### 512×512 Play Store icon

- Not part of the APK/AAB; lives in `app/android/play-store-assets/icon-512.png`. Generated from the same source as the launcher. Owned by `epic-android-play-console-launch` but listed here so the source-of-truth image is decided during hardening.

### FCM notification channel

- In `app/lib/core/services/push_notification_service.dart` (already exists), verify a notification channel is explicitly declared for Android 8+ (required) with id `palateful_default`, name "Palateful Notifications", importance `high`. If `flutter_local_notifications` already auto-creates one, confirm the ID matches what the FCM payload specifies under `android.notification.channel_id`. Otherwise add explicit `AndroidNotificationChannel(...)` creation at app init.

### Runtime notification permission prompt

- `app/lib/features/onboarding/onboarding_notification_permission_screen.dart` already prompts on iOS via `firebase_messaging`. On Android 13+, `firebase_messaging.requestPermission()` now actually triggers the OS prompt once `POST_NOTIFICATIONS` is declared. Verify it does — if it doesn't, call `permission_handler`'s `Permission.notification.request()` directly on Android.

### Auth0 + deep-link config

- Confirm `app/lib/core/services/auth_service.dart` still uses the `com.palateful.app` custom scheme for Auth0 (no change expected — the new `https` intent filter is *additive*).
- `app_router.dart` should already handle `https://palateful.app/recipes/...` paths the same as internal app navigation. Verify with a `am start -W -a android.intent.action.VIEW -d "https://palateful.app/recipes/r-123" com.palateful.palateful` command after manifest changes.

## Backend changes

None. App Links verification is a pure static-file gig on the web side (`assetlinks.json` served at `https://palateful.app/.well-known/assetlinks.json`). The API never sees the verification request — Android's verifier hits the web host directly.

## Infrastructure changes

### Web (ships with existing Cloudflare Pages deploy)

- `app/web/.well-known/assetlinks.json` — static JSON file. Contents:
  ```json
  [{
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.palateful.palateful",
      "sha256_cert_fingerprints": ["<SHA-256 of Play-managed app-signing cert>"]
    }
  }]
  ```
- The SHA-256 fingerprint comes from the Play Console → Setup → App Integrity → App signing key certificate. It's generated by Google when Play App Signing is enrolled during first AAB upload. **This means the file can only be finalized after `epic-android-play-console-launch` Story 1 runs the first manual AAB upload.** Until then, ship the file with a placeholder + TODO, or hold the final commit to this file until post-first-upload.
- Cloudflare Pages serves `.well-known/assetlinks.json` automatically if the file is in `build/web/.well-known/`. Flutter's `build web` copies `web/` → `build/web/` recursively, including dotfile-prefixed dirs, so `.well-known/` travels through cleanly. Verify with `flutter build web && ls build/web/.well-known/`.

### Firebase Crashlytics

- `app/firebase.json` → set `"uploadDebugSymbols": true` for the Android app. (Currently `false` for iOS; we toggle Android-side separately via the Gradle Crashlytics plugin config.)
- In `app/android/app/build.gradle.kts`, the `com.google.firebase.crashlytics` Gradle plugin is already applied. Add a `firebaseCrashlytics { ... }` block in the `release` build type to enable NDK symbol upload. The actual upload happens at build time via the plugin; CI just needs `FIREBASE_SERVICE_ACCOUNT_JSON` in the environment (new GitHub Secret, owned by `epic-android-ci-hardening`).

### Release-mode smoke

- `app/android/key.properties` — sample template committed at `key.properties.example` so any dev can generate a self-signed keystore and run `flutter build appbundle --release` locally to confirm the release path works pre-CI. Current repo has no example file.

## Initial design principles

- **Declare the minimum.** Every permission we remove is one fewer policy conversation. Lean on intent flags + OS-granted scoped access wherever possible.
- **Adaptive everything.** Android 13+ themed icons, Android 12+ dynamic color, Android 14 predictive-back — only the first is cheap enough to include in v1; the rest defer until device access.
- **Crashlytics must work or it's useless.** Symbolicated crashes are table stakes for a real-device beta — unsymbolicated reports are noise.
- **App Links, not chooser.** `https://palateful.app/...` should always open the app. The assetlinks.json is a one-time static file; pay the complexity once.
- **Cook timers stay exact.** SCHEDULE_EXACT_ALARM stays declared — cook timer UX requires millisecond-accurate firing. Justification copy lives in `ANDROID.md` for Play Console sensitive-permission review.

## File structure (anticipated)

### New
- `app/android/play-store-assets/icon-source-1024.png` — the single source PNG for both launcher icons (via `flutter_launcher_icons`) and the 512×512 Play Store icon (via downscale in `apl-2`).
- `app/web/.well-known/assetlinks.json` — ships with placeholder SHA-256 + TODO; real fingerprint committed after first manual AAB upload (ANDROID.md step 11–12).
- `app/android/key.properties.example` — template for a local developer to generate a keystore and run `flutter build appbundle --release`.

### Modified
- `app/android/app/src/main/AndroidManifest.xml` — add POST_NOTIFICATIONS, add https intent-filter with `autoVerify="true"`, remove READ_MEDIA_*.
- `app/android/app/build.gradle.kts` — `firebaseCrashlytics { mappingFileUploadEnabled = true; nativeSymbolUploadEnabled = true }` in release build type.
- `app/firebase.json` — Android `uploadDebugSymbols: true`.
- `app/pubspec.yaml` — add `flutter_launcher_icons` to `dev_dependencies` + configure `flutter_launcher_icons:` block.
- `app/lib/core/services/push_notification_service.dart` — eagerly create `palateful_default` channel at app init.
- `app/lib/features/onboarding/onboarding_notification_permission_screen.dart` — verify Android 13+ prompt fires via existing `firebase_messaging.requestPermission()` call (no new Android-only code path).

### Regenerated by `dart run flutter_launcher_icons`
- `app/android/app/src/main/res/mipmap-{hdpi,xhdpi,xxhdpi,xxxhdpi,mdpi}/ic_launcher.png` (overwritten with brand-aligned raster).
- `app/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` (adaptive icon XML with monochrome element).
- `app/android/app/src/main/res/drawable/ic_launcher_foreground.xml` + `values/ic_launcher_background.xml`.

## Stories

### Story 1: `arh-1` — POST_NOTIFICATIONS + runtime prompt + FCM channel

**AC:**
- Manifest declares `android.permission.POST_NOTIFICATIONS`.
- On first onboarding notification-permission step, Android 13+ shows the native OS prompt. Verified via emulator running API 33+.
- If user denies, app continues without crash; toggling in Settings → App info later re-enables.
- `palateful_default` notification channel is created explicitly on first launch (name "Palateful Notifications", importance HIGH, show badge true). Incoming FCM messages must declare matching `channel_id` in the payload (backend push config confirmed — no backend change).
- Unit test: `push_notification_service_test.dart` asserts the channel creation call happens on `Platform.isAndroid`.
- Widget test: onboarding-permission screen shows Android-specific copy path when `Platform.isAndroid`.
- Manual smoke (emulator): backend sends test push → appears in shade.

### Story 2: `arh-2` — Remove over-declared READ_MEDIA_* permissions

**AC:**
- Manifest removes `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO`.
- Inline comment on the share intent filter cluster is updated: "Shared files open via FLAG_GRANT_READ_URI_PERMISSION on the intent; no manifest permission required per Jan 2025 Play policy."
- Integration test (emulator): `am start -a android.intent.action.SEND -t image/jpeg --eu android.intent.extra.STREAM content://...` — shared handler still copies file to sandbox successfully. Covers sae-2's regression surface.
- sae-1's retrospective comment in the epic is amended in-place (annotation added) since sae-1 is marked done and this reverts part of it.
- Android Studio lint clean.

### Story 3: `arh-3` — Adaptive launcher icon via `flutter_launcher_icons`

**AC:**
- `app/android/play-store-assets/icon-source-1024.png` exists — a 1024×1024 PNG (transparent background, Palateful "P" mark centered with ~10% safe-area padding for adaptive cropping).
- `app/pubspec.yaml` adds `flutter_launcher_icons: ^X.Y.Z` to `dev_dependencies` (pin latest stable-compatible).
- `pubspec.yaml` `flutter_launcher_icons:` config block specifies: `android: true`, `image_path: app/android/play-store-assets/icon-source-1024.png`, `adaptive_icon_background: "#F5EFE6"` (cream brand hex; confirm from `app/lib/core/theme/theme.dart`), `adaptive_icon_foreground: <same>`, `min_sdk_android: 26`, optionally `image_path_android_monochrome`.
- `dart run flutter_launcher_icons` generates: `mipmap-{hdpi,xhdpi,xxhdpi,xxxhdpi,mdpi}/ic_launcher.png`, `mipmap-anydpi-v26/ic_launcher.xml` (with `<monochrome>`), `drawable/ic_launcher_foreground.xml`, `values/ic_launcher_background.xml`. All committed.
- `flutter build appbundle --release` produces an AAB where the icon renders as an adaptive icon on a Pixel 7 (API 33+) emulator — verified via screenshot diff against an existing reference icon.
- Pre-API-26 fallback preserved (raster `ic_launcher.png` in each mipmap density still present after regeneration).
- Re-run is idempotent: running `dart run flutter_launcher_icons` twice without changes produces no git diff.

### Story 4: `arh-4` — HTTPS App Links + assetlinks.json

**AC:**
- Manifest adds `<intent-filter android:autoVerify="true">` for `android:scheme="https"` + `android:host="palateful.app"`.
- `app/web/.well-known/assetlinks.json` created with placeholder fingerprint (`"<FILL-IN-AFTER-PLAY-APP-SIGNING-ENROLLMENT>"`).
- A TODO comment at the top of `assetlinks.json` references the procedure (in `ANDROID.md`) for retrieving the fingerprint from Play Console → Setup → App Integrity post-first-AAB-upload.
- After first AAB upload + fingerprint insertion, a post-merge check in CI (`epic-android-ci-hardening` Story 2) verifies `assetlinks.json` is served from `https://palateful.app/.well-known/assetlinks.json` with `content-type: application/json`.
- Integration test (emulator): `am start -W -a android.intent.action.VIEW -d "https://palateful.app/recipes/r-123" com.palateful.palateful` opens Palateful directly without a browser chooser.
- Auth0 `com.palateful.app://` callback path still works (existing behavior preserved).

### Story 5: `arh-5` — Crashlytics native symbol upload

**AC:**
- `app/firebase.json` sets Android `uploadDebugSymbols: true`.
- `app/android/app/build.gradle.kts` adds `firebaseCrashlytics { mappingFileUploadEnabled = true; nativeSymbolUploadEnabled = true }` in `buildTypes.release`.
- A release-mode build locally produces a `build/outputs/native-debug-symbols.zip` artifact.
- Fastlane Android lane (`app/fastlane/Fastfile`) gets a `crashlytics_upload_symbols` step (or equivalent `sh` call to `firebase crashlytics:symbols:upload`) after `gradle bundle` — wired by `epic-android-ci-hardening` Story 5.
- Local smoke: `flutter build appbundle --release` then open the build log; look for "Uploading native symbols" (or equivalent Gradle task output).

### Story 6: `arh-6` — Local release-mode smoke template

**AC:**
- `app/android/key.properties.example` template added with dummy values + comments explaining each field.
- `ANDROID.md` (referenced, owned by `epic-android-play-console-launch`) documents `keytool -genkeypair -v -keystore palateful-upload.jks -alias upload -keyalg RSA -keysize 2048 -validity 9125` and points back to this example.
- A local developer can copy the template, run the keytool command, fill passwords, and then `flutter build appbundle --release` succeeds, producing a signed AAB.
- `.gitignore` confirms `key.properties` is git-ignored (it already is; verify with `git check-ignore`). The *.example* file is checked in.

## Dependencies

- **Blocks `epic-android-play-console-launch`** — Play Console forms require the permissions + icon + adaptive launcher + Crashlytics to be ready before first upload.
- **Does not block `epic-android-privacy-policy-page`** — they're independent, can ship in parallel.
- **Blocks `epic-android-ci-hardening` partially** — CI wires the Fastlane Crashlytics upload step that Story 5 here prepares. CI can start in parallel; the Crashlytics-upload CI step lands after Story 5.
- **Inherits from `epic-share-android-entrypoint` (sae-1 through sae-3)**: all already landed. Story 2 (`arh-2`) amends sae-1's manifest additions.

## Open questions for the user

None — party-mode resolved: HTTPS-only App Links (no cleartext), single `palateful_default` channel in v1 (per-type split when users request muting), monochrome icon derives from the same source PNG via `flutter_launcher_icons` (plugin auto-desaturates if no separate monochrome source is provided).
