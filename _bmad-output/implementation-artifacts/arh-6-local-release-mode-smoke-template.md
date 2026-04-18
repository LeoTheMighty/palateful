# Story arh-6: Local release-mode smoke template

**Status:** ready-for-dev
**Epic:** epic-android-release-hardening

## Goal

Let any local developer run `flutter build appbundle --release`
pre-CI by providing a `key.properties.example` template and a copy of
the `keytool` incantation needed to generate a self-signed upload
keystore. Today the only path to a signed release AAB is through CI
(Fastlane-injected signing) — this story unblocks local verification
before pushing a build, which is exactly what you need when
troubleshooting arh-3 (launcher icon) or arh-5 (Crashlytics symbol
generation) output.

## Scope (from epic)

- New `app/android/key.properties.example` with dummy values +
  per-field comments.
- Keystore-generation command documented in the example file itself
  (so developers don't need to chase `ANDROID.md` — that runbook is
  owned by `apl-1`).
- Verify `key.properties` is already gitignored (it is — `app/android/.gitignore:12`).

## Implementation

### `app/android/key.properties.example`

```properties
# header comment with: purpose, gitignore guarantee, keytool command
# to generate the keystore, and pointer to ANDROID.md.

storePassword=REPLACE_WITH_KEYSTORE_PASSWORD
keyPassword=REPLACE_WITH_KEY_PASSWORD
keyAlias=upload
storeFile=/absolute/path/to/palateful-upload.jks
```

The fields mirror what `app/android/app/build.gradle.kts` reads at
`signingConfigs.release` (lines 45-55).

## Acceptance criteria (from epic)

- [x] `app/android/key.properties.example` exists with dummy values +
  comments explaining each field.
- [x] `keytool -genkeypair -v -keystore palateful-upload.jks
  -alias upload -keyalg RSA -keysize 2048 -validity 9125` is
  documented in the example file's header comment.
- [ ] End-to-end smoke (dev copies template, generates keystore, runs
  `flutter build appbundle --release`, gets a signed AAB) — deferred
  to QA walkthrough.
- [x] `.gitignore` confirms `key.properties` is git-ignored (verified
  via `git check-ignore -v app/android/key.properties` →
  `app/android/.gitignore:12:key.properties`). The `.example` file is
  NOT ignored (verified the same way) and is therefore checked in.

## QA walkthrough

Split into `arh-6-qa-walkthrough.md`.

## File list

### New

- `app/android/key.properties.example`
