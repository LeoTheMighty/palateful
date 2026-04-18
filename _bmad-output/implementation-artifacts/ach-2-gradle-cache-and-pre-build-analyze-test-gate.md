# Story ach-2: Gradle cache + pre-build analyze + test gate

**Status:** ready-for-dev
**Epic:** epic-android-ci-hardening

## Goal

Two cuts to `android-build`:

1. **Gradle cache**: every cold run redownloads `~/.gradle/caches` +
   `~/.gradle/wrapper` dependencies. That's 3–5 minutes of dead time
   per build. Cache keyed on `hashFiles('app/android/**/*.gradle*',
   'app/android/gradle/wrapper/gradle-wrapper.properties',
   'app/pubspec.lock')` so any gradle/pubspec change invalidates.

2. **Fail-fast analyze + test**: today a broken main can be tagged and
   shipped to internal track because there is no gate between
   `flutter pub get` and `gradle bundle`. Add `flutter analyze
   --no-fatal-warnings --no-fatal-infos` + `flutter test` before the
   Fastlane invocation so a red suite stops the build.

## Implementation

### `.github/workflows/mobile-builds.yml` — `android-build` job

Insert after the existing `Install Flutter dependencies` step, before
`Set up Ruby and Bundler`:

```yaml
- name: Cache Gradle
  uses: actions/cache@v4
  with:
    path: |
      ~/.gradle/caches
      ~/.gradle/wrapper
    key: gradle-${{ runner.os }}-${{ hashFiles('app/android/**/*.gradle*', 'app/android/gradle/wrapper/gradle-wrapper.properties', 'app/pubspec.lock') }}
    restore-keys: |
      gradle-${{ runner.os }}-

- name: Flutter analyze
  working-directory: app
  run: flutter analyze --no-fatal-warnings --no-fatal-infos

- name: Flutter test
  working-directory: app
  run: flutter test
```

## Acceptance criteria

- [x] `actions/cache@v4` step for `~/.gradle/caches` + `~/.gradle/wrapper`
  keyed on gradle + pubspec hash with a runner-scoped restore-key.
- [x] `flutter analyze --no-fatal-warnings --no-fatal-infos` and
  `flutter test` steps before `bundle exec fastlane android internal`.
- [ ] Second cold run shows Gradle cache hit (deferred to first post-
  merge tag push — reading the `Cache hit` log line).
- [ ] Contrived broken-PR test that analyze blocks the upload —
  deferred to `ach-6`'s YOLO acceptance doc entry; the path is covered
  by the same pre-flight runbook.

## Why `--no-fatal-warnings --no-fatal-infos`

`ci.yml`'s flutter-test job already uses the same flags. Warnings
(unused private methods, dead params) are worth surfacing but don't
block the release path. Errors (type errors, undefined names) still
fail, which is what we want.

## File list

### Modified

- `.github/workflows/mobile-builds.yml`
