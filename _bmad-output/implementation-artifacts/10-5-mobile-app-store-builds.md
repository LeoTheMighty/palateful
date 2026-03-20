# Story 10.5: Mobile App Store Builds

Status: done

## Story

As a developer,
I want automated mobile build pipelines for iOS and Android,
so that the app can be published to TestFlight and Play Store reliably.

## Acceptance Criteria

1. **iOS build via Fastlane** — When the build pipeline runs via Fastlane, an iOS build is generated and uploaded to TestFlight.
2. **Android build via Fastlane** — A signed Android build (AAB) is generated and uploaded to Play Store internal testing track.
3. **Build signing configured** — iOS code signing and Android keystore signing are configured for both platforms, usable in CI.
4. **Pipeline trigger** — The mobile build workflow can be triggered manually (`workflow_dispatch`) OR automatically on tagged releases (e.g., `v*.*.*` tags pushed to main).
5. **No regressions** — Existing CI jobs (lint, test, flutter-test, docker build, terraform) continue passing.

## Tasks / Subtasks

- [x] Task 1: Set up Fastlane in `app/` directory (AC: 1, 2)
  - [x] Create `app/fastlane/Fastfile` with `:ios` and `:android` lanes
  - [x] Create `app/fastlane/Appfile` with app identifiers
  - [x] Create `app/Gemfile` with fastlane gem dependency
  - [x] Add `app/Gemfile.lock` (generated via `bundle lock`)

- [x] Task 2: Configure iOS code signing (AC: 1, 3)
  - [x] Add Fastlane `match` support for CI (readonly in CI via `is_ci`)
  - [x] Update iOS lane to use `build_ios_app` (gym) for IPA generation
  - [x] Upload to TestFlight via `upload_to_testflight`
  - [x] Document required secrets: `MATCH_PASSWORD`, `MATCH_GIT_URL`, `APP_STORE_CONNECT_API_KEY_*`

- [x] Task 3: Configure Android signing (AC: 2, 3)
  - [x] Update `app/android/app/build.gradle.kts` with `key.properties`-based release signing config
  - [x] Add Android lane using `gradle` action with `android.injected.signing.*` properties
  - [x] Upload to Play Store internal track via `upload_to_play_store`
  - [x] Document required secrets: `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `ANDROID_STORE_PASSWORD`, `PLAY_STORE_JSON_KEY`

- [x] Task 4: Create GitHub Actions mobile build workflow (AC: 4, 5)
  - [x] Create `.github/workflows/mobile-builds.yml`
  - [x] Add `workflow_dispatch` trigger (manual)
  - [x] Add `push` trigger on `v*.*.*` tag pattern
  - [x] iOS job: macOS-latest runner, Flutter 3.32.0-0.3.pre master, CocoaPods, `ruby/setup-ruby@v1` with `bundler-cache`, `bundle exec fastlane ios beta`
  - [x] Android job: ubuntu-latest runner, Java 17 temurin, Flutter 3.32.0-0.3.pre master, `ruby/setup-ruby@v1`, `bundle exec fastlane android internal`
  - [x] Load all secrets from GitHub Actions secrets

- [x] Task 5: Verify and document (AC: 5)
  - [x] `ci.yml` is unmodified and all existing tests pass (Flutter test suite: exit 0)
  - [x] Fastfile header documents all required secrets for iOS and Android

## Dev Notes

### Architecture Constraints
- **Fastlane is the designated tool** — architecture mandates Fastlane for iOS TestFlight and Android Play Store. No alternatives.
- **GitHub Actions orchestrates** — mobile builds must live in `.github/workflows/mobile-builds.yml` (separate from `.github/workflows/ci.yml` which handles lint/test/docker).
- **Two environments only** — Local (Docker Compose) and Prod (AWS). No staging. Mobile builds go directly to TestFlight (iOS) and Play Store internal track (Android).
- **Flutter master channel** — CI uses `flutter-version: '3.32.0-0.3.pre'` with `channel: master`. Use same in mobile workflow.

### Existing Project Structure

```
palateful/
├── app/
│   ├── android/
│   │   └── app/
│   │       └── build.gradle.kts   ← needs signing config for release
│   ├── ios/
│   │   ├── Podfile                ← iOS 14 minimum
│   │   └── Runner.xcodeproj/
│   ├── pubspec.yaml               ← Flutter ^3.9.0-51.0.dev master
│   └── fastlane/                  ← CREATE THIS DIRECTORY
│       ├── Fastfile               ← CREATE
│       └── Appfile                ← CREATE
├── app/Gemfile                    ← CREATE
├── .github/
│   └── workflows/
│       ├── ci.yml                 ← DO NOT MODIFY
│       └── mobile-builds.yml      ← CREATE
```

### Android Signing Pattern (build.gradle.kts)

The current `app/android/app/build.gradle.kts` uses debug signing for release (`TODO: Add proper signing`). Replace with keystore-from-env pattern:

```kotlin
// In android { ... signingConfigs { ... } }
signingConfigs {
    create("release") {
        storeFile = file(System.getenv("ANDROID_KEYSTORE_PATH") ?: "keystore/release.jks")
        storePassword = System.getenv("ANDROID_STORE_PASSWORD") ?: ""
        keyAlias = System.getenv("ANDROID_KEY_ALIAS") ?: ""
        keyPassword = System.getenv("ANDROID_KEY_PASSWORD") ?: ""
    }
}
buildTypes {
    release {
        signingConfig = signingConfigs.getByName("release")
        isMinifyEnabled = true
        proguardFiles(...)
    }
}
```

In CI: decode base64 keystore from secret, write to temp file, set `ANDROID_KEYSTORE_PATH`.

### Fastfile Structure

```ruby
# app/fastlane/Fastfile
default_platform(:ios)

platform :ios do
  desc "Build and upload to TestFlight"
  lane :beta do
    setup_ci if ENV['CI']
    match(type: "appstore", readonly: is_ci)
    build_ios_app(
      scheme: "Runner",
      workspace: "ios/Runner.xcworkspace",
      export_method: "app-store"
    )
    upload_to_testflight(skip_waiting_for_build_processing: true)
  end
end

platform :android do
  desc "Build and upload to Play Store internal track"
  lane :internal do
    gradle(
      task: "bundle",
      build_type: "Release",
      project_dir: "android/"
    )
    upload_to_play_store(
      track: "internal",
      aab: "android/app/build/outputs/bundle/release/app-release.aab"
    )
  end
end
```

### Appfile

```ruby
# app/fastlane/Appfile
app_identifier("com.palateful.palateful")   # iOS bundle ID = Android package ID
apple_id("") # Set via APP_STORE_CONNECT_USER or API key
```

### Gemfile

```ruby
# app/Gemfile
source "https://rubygems.org"
gem "fastlane"
```

### GitHub Actions Mobile Workflow Template

```yaml
# .github/workflows/mobile-builds.yml
name: Mobile App Store Builds

on:
  workflow_dispatch:
  push:
    tags:
      - 'v*.*.*'

jobs:
  ios-build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.32.0-0.3.pre'
          channel: 'master'
      - name: Install Ruby dependencies
        working-directory: app
        run: bundle install
      - name: Install CocoaPods
        working-directory: app/ios
        run: pod install
      - name: Build and upload to TestFlight
        working-directory: app
        run: bundle exec fastlane ios beta
        env:
          MATCH_PASSWORD: ${{ secrets.MATCH_PASSWORD }}
          MATCH_GIT_URL: ${{ secrets.MATCH_GIT_URL }}
          APP_STORE_CONNECT_API_KEY_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          APP_STORE_CONNECT_API_KEY_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          APP_STORE_CONNECT_API_KEY_KEY: ${{ secrets.ASC_PRIVATE_KEY }}

  android-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.32.0-0.3.pre'
          channel: 'master'
      - name: Decode keystore
        run: |
          echo "${{ secrets.ANDROID_KEYSTORE_BASE64 }}" | base64 --decode > app/android/keystore/release.jks
      - name: Install Ruby dependencies
        working-directory: app
        run: bundle install
      - name: Build and upload to Play Store
        working-directory: app
        run: bundle exec fastlane android internal
        env:
          ANDROID_KEYSTORE_PATH: android/keystore/release.jks
          ANDROID_STORE_PASSWORD: ${{ secrets.ANDROID_STORE_PASSWORD }}
          ANDROID_KEY_ALIAS: ${{ secrets.ANDROID_KEY_ALIAS }}
          ANDROID_KEY_PASSWORD: ${{ secrets.ANDROID_KEY_PASSWORD }}
          SUPPLY_JSON_KEY_DATA: ${{ secrets.PLAY_STORE_JSON_KEY }}
```

### Required GitHub Secrets

Document these in the story completion notes — they must be manually added to the repo:

**iOS:**
- `MATCH_PASSWORD` — Fastlane Match encryption password
- `MATCH_GIT_URL` — Git repo URL for certificates (or use App Store Connect API key approach)
- `APP_STORE_CONNECT_API_KEY_KEY_ID` — App Store Connect API key ID
- `APP_STORE_CONNECT_API_KEY_ISSUER_ID` — App Store Connect issuer ID
- `APP_STORE_CONNECT_API_KEY_KEY` — App Store Connect private key (.p8 file content)

**Android:**
- `ANDROID_KEYSTORE_BASE64` — Base64-encoded release keystore `.jks` file
- `ANDROID_STORE_PASSWORD` — Keystore password
- `ANDROID_KEY_ALIAS` — Key alias in keystore
- `ANDROID_KEY_PASSWORD` — Key password
- `PLAY_STORE_JSON_KEY` — Google Play service account JSON key

### iOS Signing Approach

Use **Fastlane Match** (recommended) or manual certificate approach:
- Match uses a private git repo to store encrypted certificates and profiles
- In CI: `match(type: "appstore", readonly: true)` — reads from repo, no generation
- `setup_ci` ensures keychain is configured on macOS runner

Alternative if Match is not set up: use App Store Connect API key directly with `app_store_connect_api_key` action.

### Android Package Name
- Package: `com.palateful.palateful` (from `app/android/app/build.gradle.kts`)
- The keystore directory `app/android/keystore/` should be in `.gitignore`

### Key Files to NOT Touch
- `app/lib/` — no Flutter source changes needed for this story
- `app/test/` — no test changes needed
- `app/ios/Podfile` — already configured for iOS 14 minimum
- `.github/workflows/ci.yml` — do not modify

### Firebase Context
Firebase is already configured (`google-services.json` for Android, `GoogleService-Info.plist` for iOS). No changes needed — FCM push notifications work via existing config.

### Project Structure Notes
- Story 10.4 added responsive layout; 10.5 is orthogonal — pure CI/DevOps, no Flutter source changes
- Flutter master channel dependency: pubspec.yaml uses `^3.9.0-51.0.dev`; CI uses `3.32.0-0.3.pre` on master. Keep consistent.
- Android `build.gradle.kts` uses Kotlin DSL (not Groovy). Signing config syntax must be Kotlin DSL (`create("release")`, not `release { ... }`).

### References
- Architecture: mobile builds via Fastlane [Source: _bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment]
- CI/CD current setup [Source: .github/workflows/ci.yml]
- Android build config [Source: app/android/app/build.gradle.kts]
- iOS Podfile min version [Source: app/ios/Podfile]
- App package name [Source: app/android/app/build.gradle.kts — defaultConfig.applicationId]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented Fastlane setup from scratch: `app/Gemfile`, `app/Gemfile.lock`, `app/fastlane/Fastfile`, `app/fastlane/Appfile`
- iOS lane (`fastlane ios beta`): uses `setup_ci`, `app_store_connect_api_key`, `match(readonly: is_ci)`, `build_ios_app`, `upload_to_testflight`
- Android lane (`fastlane android internal`): decodes base64 keystore to `/tmp`, calls `gradle(bundle)` with `android.injected.signing.*` properties, uploads AAB via `upload_to_play_store`
- `app/android/app/build.gradle.kts` updated: removed debug signing fallback TODO, added `key.properties`-based release `signingConfig` with env var fallback comment
- `mobile-builds.yml` triggers: `workflow_dispatch` + `push` on `v*.*.*` tags; iOS on `macos-latest`, Android on `ubuntu-latest`; both use `ruby/setup-ruby@v1` with `bundler-cache: true`
- All required secrets documented in Fastfile header and workflow file header comment
- Existing Flutter test suite passes (exit code 0, no regressions); `ci.yml` untouched
- Gemfile.lock generated via `bundle lock` (requires Ruby 2.6 bundler 2.4.22 user install); `ruby/setup-ruby@v1` in CI will use Ruby 3.3 and regenerate if needed
- `android.injected.signing.*` Gradle properties are the standard Fastlane approach — override signing in build.gradle.kts without modifying it at build time

### File List

- `app/Gemfile` (new)
- `app/Gemfile.lock` (new)
- `app/fastlane/Fastfile` (new)
- `app/fastlane/Appfile` (new)
- `app/android/app/build.gradle.kts` (modified — added key.properties-based release signing config)
- `.github/workflows/mobile-builds.yml` (new)
- `_bmad-output/implementation-artifacts/10-5-mobile-app-store-builds.md` (this file)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (updated)
