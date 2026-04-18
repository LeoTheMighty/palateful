# QA walkthrough — arh-5: Crashlytics native symbol upload config

## Smoke prerequisites

- A local `app/android/key.properties` with a generated upload
  keystore (see `arh-6`). Alternative: pass
  `android.injected.signing.*` Gradle properties to mimic Fastlane.
- `FIREBASE_SERVICE_ACCOUNT_JSON` env var only needed when you want
  the actual upload step to fire — pure local compile does not upload.

## Checklist — local compile

- [ ] From `app/`, run `flutter build appbundle --release`. Build
      completes without errors.
- [ ] Inspect the build output:
  - [ ] `build/app/outputs/bundle/release/app-release.aab` exists.
  - [ ] `build/app/outputs/native-debug-symbols.zip` exists
        (Crashlytics NDK artifact — produced because
        `nativeSymbolUploadEnabled = true`).
  - [ ] `build/app/outputs/mapping/release/mapping.txt` exists
        (R8-produced, required for Kotlin/Java obfuscation
        mapping — produced because `mappingFileUploadEnabled = true`).
- [ ] Run `./gradlew -q :app:tasks --group Crashlytics` (from
      `app/android/`). Confirm tasks named
      `uploadCrashlyticsMappingFileRelease` and
      `uploadCrashlyticsSymbolFileRelease` appear — their presence
      proves the extension is configured and the plugin saw it.

## Checklist — CI upload (post-ach-3)

- [ ] `ach-3` wires Fastlane `crashlytics_upload_symbols` lane. When
      that lands, a CI build run should show "Uploading native
      symbols" (or the equivalent Gradle task log line) after
      `gradle bundle`.
- [ ] Post-upload, Firebase console → Crashlytics → Dashboard shows
      the new app version's symbol set.

## Regression surface

- **Release build time**: native symbol generation adds ~30-60s to a
  release bundle on a dev laptop. Acceptable trade; noted here so the
  "why is my release build slower?" question has an answer.
- **APK/AAB size**: unchanged. Symbols are uploaded separately, not
  bundled.

## Out of scope

- iOS Crashlytics debug symbol upload (`uploadDebugSymbols: false`
  remains on iOS; handled by the iOS deploy lane separately).
- Fastlane integration (`ach-3`).
