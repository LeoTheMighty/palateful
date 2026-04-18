# QA walkthrough — ach-2 (Gradle cache + pre-build analyze + test gate)

**Epic:** epic-android-ci-hardening

## What shipped

- `.github/workflows/mobile-builds.yml` — `android-build` job:
  - New `Cache Gradle` step for `~/.gradle/caches` + `~/.gradle/wrapper`,
    keyed on `hashFiles('app/android/**/*.gradle*',
    'app/android/gradle/wrapper/gradle-wrapper.properties',
    'app/pubspec.lock')` with a runner-scoped restore fallback.
  - `Install Flutter dependencies` step now writes dummy env values to
    `.env` (matches `ci.yml` flutter-test pattern) so analyze/test can
    run without real secrets.
  - New `Flutter analyze` step:
    `flutter analyze --no-fatal-warnings --no-fatal-infos`.
  - New `Flutter test` step: `flutter test`.
  - All three new steps run before the Fastlane invocation, so a
    failing analyze/test stops the build before any signing or upload.

## Static verification

1. `grep -n "actions/cache@v4" .github/workflows/mobile-builds.yml`
   shows the new Gradle entry below the existing pub cache.
2. `grep -n "flutter analyze\|flutter test" .github/workflows/mobile-builds.yml`
   shows two steps inside `android-build`, both before
   `bundle exec fastlane android internal`.
3. YAML is valid: `python3 -c "import yaml; yaml.safe_load(open(...))"`.

## Live verification (deferred to first tag push)

- **Cache hit on second run** — the first tag push after this change
  is a cache miss (expected). The second tag push should show
  `Cache hit: gradle-...` in the step summary. ~3–5 minutes shaved.
- **Fail-fast gate** — a contrived broken PR merged to main (e.g. a
  renamed function without its callers updated) should cause the next
  tag to fail at the `Flutter analyze` step, before any Gradle or
  Play Store interaction. Roll-forward: fix main, re-tag.

## Non-regressions

- iOS-build job untouched.
- No secret rotation.
- No Fastlane / Gradle file changes.

## Rollback

Single-commit revert. No external state mutated.
