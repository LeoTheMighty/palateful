# Story ach-3: Crashlytics native symbol upload via Gradle plugin + CI auth

**Status:** ready-for-dev
**Epic:** epic-android-ci-hardening

## Goal

Ship Crashlytics mapping + native debug symbols from every CI
release-mode build so Firebase can symbolicate the release stacks
testers will generate. The Gradle side is already wired (arh-5 landed
`firebaseCrashlytics { mappingFileUploadEnabled = true;
nativeSymbolUploadEnabled = true }` on `buildTypes.release`). What the
plugin still needs is a `GOOGLE_APPLICATION_CREDENTIALS` env var
pointing at a JSON key with Firebase Crashlytics access — so it can
actually talk to the upload API at build time.

## Implementation

### `.github/workflows/mobile-builds.yml` — `android-build` job

Add `google-github-actions/auth@v2` between `Cache Gradle` and
`Flutter analyze`. The step writes the service-account JSON to a
runner-tmp path and exports `GOOGLE_APPLICATION_CREDENTIALS` for all
subsequent steps. The Gradle plugin's auto-upload picks it up during
`gradle bundle`.

```yaml
- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v2
  with:
    credentials_json: ${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}
```

No separate `setup-gcloud` step yet — that lands in ach-4 for the
Firebase Test Lab invocation.

### Gradle plugin behavior — no Fastlane change needed

The `com.google.firebase.crashlytics` plugin (already applied in
`app/android/app/build.gradle.kts`) auto-uploads mapping + native
symbols during `gradle bundle` when:

1. `mappingFileUploadEnabled = true` — ✅ wired in arh-5.
2. `nativeSymbolUploadEnabled = true` — ✅ wired in arh-5.
3. `GOOGLE_APPLICATION_CREDENTIALS` env var points at a
   Firebase-authorized JSON — ✅ wired here.

If the upload fails (e.g. the SA lost its `firebase.crashlytics.access`
role), the Gradle plugin logs a warning and continues — the AAB still
builds. This is intentional: a symbol-upload outage should never block
a release.

No `upload_symbols_to_crashlytics` Fastlane call. No `firebase
crashlytics:symbols:upload` shell step. Belt-and-suspenders upload paths
create drift between the local `flutter build appbundle --release`
flow and CI.

## Acceptance criteria

- [x] `google-github-actions/auth@v2` step in `android-build` ahead
  of Gradle build, reading `FIREBASE_SERVICE_ACCOUNT_JSON`.
- [x] No Fastlane `upload_symbols_to_crashlytics` call.
- [x] Secrets header documents `FIREBASE_SERVICE_ACCOUNT_JSON`
  (landed in ach-1 header update).
- [ ] Firebase Console verification — deferred to first tag push. On
  green, Crashlytics → Palateful Android → Versions list shows the
  new version code with symbols uploaded.
- [x] Graceful degradation: Gradle plugin warns but does not abort on
  upload failure — default plugin behavior, no extra config needed.

## Security notes

- `google-github-actions/auth@v2` writes the JSON to a runner-scoped
  tmp path, not persisted to the checkout. The `credentials_json`
  input goes through GitHub's secret masking for logs.
- The same `FIREBASE_SERVICE_ACCOUNT_JSON` is planned to double as the
  Test Lab + Play Store upload identity (locked-decision 5 in the
  epic). Least-privilege rotation is tracked in ANDROID.md Section 6.

## File list

### Modified

- `.github/workflows/mobile-builds.yml`
