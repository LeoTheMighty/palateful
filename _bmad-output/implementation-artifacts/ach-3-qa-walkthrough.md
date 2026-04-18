# QA walkthrough — ach-3 (Crashlytics native symbol upload via CI auth)

**Epic:** epic-android-ci-hardening

## What shipped

- `.github/workflows/mobile-builds.yml` — `android-build` job:
  - New `Authenticate to Google Cloud` step using
    `google-github-actions/auth@v2` with
    `credentials_json: ${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}`.
  - Positioned between `Cache Gradle` and `Install Flutter
    dependencies`, so `GOOGLE_APPLICATION_CREDENTIALS` is set before
    both the analyze/test gate and the Gradle bundle invocation.

## Static verification

1. `grep -n "google-github-actions/auth@v2" .github/workflows/mobile-builds.yml`
   returns one match in the `android-build` job.
2. `grep -n "FIREBASE_SERVICE_ACCOUNT_JSON" .github/workflows/mobile-builds.yml`
   — both the secrets header and the `credentials_json` line.
3. No `upload_symbols_to_crashlytics` anywhere in `app/fastlane/`.

## Pre-flight for the operator (one-time)

Before the first tag push after this change lands:

1. Confirm the GitHub Secret `FIREBASE_SERVICE_ACCOUNT_JSON` exists and
   holds the JSON body of a service account with the
   `firebase.crashlytics.access` role (plus Test Lab + Play Store if
   reusing the same key per locked-decision 5).
2. Confirm `mappingFileUploadEnabled = true` +
   `nativeSymbolUploadEnabled = true` are still on
   `buildTypes.release` in `app/android/app/build.gradle.kts` (arh-5).

## Live verification (deferred to first tag push)

- Workflow `Authenticate to Google Cloud` step succeeds, logs
  `Successfully configured GitHub Actions credentials`.
- During `gradle bundle`, Gradle logs something like
  `Uploaded native symbols for <BUILD-ID>` (or a warn line if the
  upload quietly fails — non-fatal).
- Firebase Console → Crashlytics → Palateful Android → Versions list
  shows the new version code with the symbol icon.

## Graceful-degradation test

If the GitHub Secret is missing or the SA lacks `firebase.crashlytics
.access`, the Gradle plugin logs a warning and the build continues.
The AAB still uploads to Play Store internal track — just without
symbols. Fix the SA, push a new tag.

## Non-regressions

- No change to Fastlane.
- No change to iOS-build.
- No change to existing secrets.

## Rollback

Single-commit revert. `GOOGLE_APPLICATION_CREDENTIALS` will just not
be set, and the Gradle plugin falls back to warn-and-continue.
