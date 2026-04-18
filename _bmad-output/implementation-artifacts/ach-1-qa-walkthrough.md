# QA walkthrough — ach-1 (Unify Flutter channel + version + concurrency)

**Epic:** epic-android-ci-hardening

## What shipped

- `.github/workflows/mobile-builds.yml`:
  - Added workflow-level `env:` block: `FLUTTER_CHANNEL: stable`,
    `FLUTTER_VERSION: '3.32.0'`.
  - Both `ios-build` and `android-build` `subosito/flutter-action@v2`
    steps now read `${{ env.FLUTTER_VERSION }}` + `${{ env.FLUTTER_CHANNEL }}`.
  - `android-build` now declares `concurrency: { group:
    mobile-builds-android, cancel-in-progress: false }`.
  - Header secrets block documents `FIREBASE_SERVICE_ACCOUNT_JSON` (fed
    by ach-3).

## What to verify

Live verification requires a tag push (see Section 18 of ANDROID.md).
Static verification the operator can do now:

1. Open `.github/workflows/mobile-builds.yml` — `env:` block is right
   below the `on:` trigger, before `jobs:`.
2. `grep "channel: master"` returns nothing — master-channel pin is
   fully removed.
3. `grep "flutter-version: '3\."` returns nothing outside the `env:`
   block — no inline version pins.
4. `android-build` job reads `concurrency:` block with
   `cancel-in-progress: false`.
5. `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/mobile-builds.yml'))"` succeeds.

## End-to-end smoke (YOLO — deferred)

The first real `v*.*.*` tag push is the pipeline verification. Watch
the Actions tab; both ios-build and android-build should log the same
Flutter version during `flutter doctor`. A double-tag test (push tag
twice in quick succession, second time with a force-update) will
serialize cleanly — the second job should queue behind the first,
not cancel it.

## Known non-regressions

- No app code touched. `flutter analyze` / `flutter test` locally are
  unaffected.
- No iOS-side behavior change — matching version pin only.
- No secret rotation required.

## Rollback

Single-commit revert. No external state (Play Console, Firebase) was
mutated.
