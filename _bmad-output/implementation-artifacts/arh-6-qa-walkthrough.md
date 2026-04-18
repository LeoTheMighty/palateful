# QA walkthrough — arh-6: Local release-mode smoke template

## Smoke prerequisites

- Java JDK ≥ 17 installed (`keytool` lives in `$JAVA_HOME/bin/`).
- `flutter` on PATH.
- `app/` directory is the working directory for `flutter` commands.

## Checklist — first-time developer

- [ ] From `app/android/`, copy the template:
      `cp key.properties.example key.properties`.
- [ ] Open `key.properties` — confirm the four fields are present with
      `REPLACE_WITH_*` placeholders.
- [ ] Generate a self-signed upload keystore following the header
      comment:
      ```
      keytool -genkeypair -v \
        -keystore palateful-upload.jks \
        -alias upload \
        -keyalg RSA -keysize 2048 -validity 9125
      ```
      Store the keystore OUTSIDE the repo (e.g. `~/.android-keystores/`).
      `keytool` prompts for a store password + key password interactively.
- [ ] Edit `key.properties` — set `storePassword`, `keyPassword`,
      leave `keyAlias=upload`, set `storeFile` to the absolute path of
      the keystore.
- [ ] `git status` should NOT list `key.properties` (gitignore
      guarantee). If it does, `app/android/.gitignore` has been
      changed — investigate before committing anything.
- [ ] From `app/`, run `flutter build appbundle --release`. Build
      completes, produces
      `app/build/app/outputs/bundle/release/app-release.aab`.
- [ ] Optional: confirm signature:
      `jarsigner -verify -verbose -certs app-release.aab` shows the
      upload certificate with the alias `upload`.

## Regression surface

- **CI**: Fastlane-injected signing continues to work because
  `build.gradle.kts` falls back to the debug signing config when
  `key.properties` is absent, then Fastlane overrides via
  `android.injected.signing.*` Gradle properties. No CI change.

## Out of scope

- ANDROID.md runbook (owned by `apl-1` in
  `epic-android-play-console-launch`).
- Play App Signing enrolment (owned by `apl-1`).
