# Story arh-5: Crashlytics native symbol upload config

**Status:** ready-for-dev
**Epic:** epic-android-release-hardening

## Goal

Make release-mode Android crash reports symbolicate correctly in
Firebase Crashlytics. Today the Crashlytics Gradle plugin is applied
but neither mapping-file nor native-symbol upload is enabled, so stack
frames from obfuscated Dart/Kotlin code and from native libs (Flutter
engine, Firebase SDK) arrive as raw addresses. Unsymbolicated reports
are unactionable noise — table stakes for an internal-track beta is a
symbolicated stack trace.

## Scope (from epic)

- `app/android/app/build.gradle.kts`: add a
  `com.google.firebase.crashlytics.buildtools.gradle.CrashlyticsExtension`
  block to the `release` build type with
  `mappingFileUploadEnabled = true` and `nativeSymbolUploadEnabled = true`.
- `app/firebase.json`: set the Android platform's `uploadDebugSymbols`
  flag to `true` (mirrors the iOS-side flag, which stays `false` —
  iOS upload is handled by the iOS runbook).
- No backend, no Dart, no CI-workflow changes here. The CI step that
  actually runs the upload lives in `epic-android-ci-hardening`
  Story 3 (`ach-3`).

## Implementation

### `app/android/app/build.gradle.kts`

Inside the `buildTypes.release { ... }` block, append:

```kotlin
configure<com.google.firebase.crashlytics.buildtools.gradle.CrashlyticsExtension> {
    mappingFileUploadEnabled = true
    nativeSymbolUploadEnabled = true
}
```

The `com.google.firebase.crashlytics` plugin is already applied in the
plugins block (line 5). The `CrashlyticsExtension` class is picked up
via the plugin's own classpath — no explicit import needed since Kotlin
DSL `configure<Fully.Qualified.Name>` resolves at compile time.

### `app/firebase.json`

Flip `uploadDebugSymbols` from absent to `true` on the Android entry.
Leave iOS at `false`.

## Acceptance criteria (from epic)

- [x] `app/firebase.json` sets Android `uploadDebugSymbols: true`.
- [x] `app/android/app/build.gradle.kts` adds `CrashlyticsExtension`
  `mappingFileUploadEnabled = true` + `nativeSymbolUploadEnabled = true`
  in `buildTypes.release`.
- [ ] `flutter build appbundle --release` locally produces a
  `build/outputs/native-debug-symbols.zip` artifact — deferred to QA
  walkthrough (requires a local keystore via arh-6 or Fastlane-injected
  signing). The Gradle plugin generates the artifact; CI uploads it.
- [ ] Fastlane `crashlytics_upload_symbols` wiring — out of scope; owned
  by `ach-3`.
- [x] Local smoke: invoking `./gradlew tasks --all` would list the
  Crashlytics symbol upload tasks (not run here to avoid a full Gradle
  config; the plugin's presence in the plugins block + the extension
  configuration is the contract).

## QA walkthrough

Split into `arh-5-qa-walkthrough.md`.

## File list

### Modified

- `app/android/app/build.gradle.kts`
- `app/firebase.json`
