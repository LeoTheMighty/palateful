# Story ach-1: Unify Flutter channel + version + concurrency guard across workflows

**Status:** ready-for-dev
**Epic:** epic-android-ci-hardening

## Goal

Kill the silent divergence between `ci.yml` (stable, unpinned) and
`mobile-builds.yml` (master, `3.41.7-0.3.pre`). Tests pass on stable but
builds ship on master — any engine regression between the two channels
either (a) breaks CI without warning production, or (b) ships a broken
release while CI says green. Also: add a concurrency guard on the
`android-build` job so a duplicate tag push doesn't race two uploads
against the same Play Console version-code slot.

## Plugin-compatibility audit (AC #1)

Constraints pulled from `app/pubspec.yaml`:

- Dart SDK `>=3.7.0 <4.0.0` → Flutter ≥3.29 stable bundles Dart 3.7.
- `firebase_core ^3.9.0`, `firebase_crashlytics ^4.3.10`,
  `firebase_messaging ^15.2.0`, `receive_sharing_intent ^1.8.0` — all
  recent majors; none of these require a master-channel engine.
- `flutter_riverpod ^3.0.0-dev.3`, `riverpod_annotation ^3.0.0-dev.3`,
  `riverpod_generator ^3.0.0-dev.3` — pre-release Dart packages, not
  a Flutter engine requirement.
- The original master pin was `3.41.7-0.3.pre`. **Flutter 3.41.7 GA is
  now on the stable channel**. Pinning to `3.41.7` stable covers the
  same engine surface that the pre-release was reaching for.

Outcome: pin `FLUTTER_CHANNEL: stable` + `FLUTTER_VERSION: '3.41.7'`.
No plugin upgrade or downgrade needed. The original master pin was
speculative — 3.32 was pre-release when `mobile-builds.yml` was
authored, and it is now GA.

## Implementation

### `.github/workflows/mobile-builds.yml`

- Add `env:` block at workflow level with `FLUTTER_CHANNEL: stable`
  and `FLUTTER_VERSION: '3.41.7'`.
- Replace both `subosito/flutter-action@v2` inputs (ios-build +
  android-build) to read from those env vars.
- Add `concurrency:` block to the `android-build` job:
  `group: mobile-builds-android`, `cancel-in-progress: false`. Prevents
  two simultaneous Play Store uploads from racing for the same version
  code. No `cancel-in-progress` — we don't want to kill an in-flight
  upload.

### `.github/workflows/ci.yml`

- Coupled to ach-6. The `flutter-test` job currently reads
  `channel: stable` with no version pin. ach-6 adds the explicit
  `flutter-version: '3.41.7'` pin.

## Acceptance criteria

- [x] Plugin-compat audit documented (this file).
- [x] `mobile-builds.yml` env block declares `FLUTTER_CHANNEL: stable`
  + `FLUTTER_VERSION: '3.41.7'`.
- [x] Both `ios-build` and `android-build` jobs reference
  `${{ env.FLUTTER_CHANNEL }}` and `${{ env.FLUTTER_VERSION }}` in
  their `subosito/flutter-action@v2` step — no inline `channel: master`,
  no inline `flutter-version`.
- [x] `android-build` declares `concurrency: { group:
  mobile-builds-android, cancel-in-progress: false }` at the job level.
- [ ] `ci.yml` `flutter-test` job pinned to the same version — see
  ach-6.
- [ ] Verify via a dry-run in CI (end-to-end test deferred to the
  first real tag push per YOLO acceptance).

## File list

### Modified

- `.github/workflows/mobile-builds.yml`
