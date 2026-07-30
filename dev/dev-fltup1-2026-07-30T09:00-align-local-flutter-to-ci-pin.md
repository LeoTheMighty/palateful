---
hash: fltup1
type: dev
created: 2026-07-30T09:00:00-06:00
title: Upgrade local Flutter toolchain to the repo's pinned stable (3.41.7)
from: debug/debug-e2edwds-2026-07-27T19:00-dwds-chrome150-attach-failure.md
status: in-progress
owner: /devx-2026-07-30T1034-61063
---

## Goal

Bring the local development Flutter toolchain up to **3.41.7 stable** — the
version CI has already been pinned to since `ach-1` — and confirm whether that
resolves the dwds ↔ Chrome 150 attach failure blocking `bqa102`'s headline AC.

This is an alignment task, not a version-selection one. Local is the outlier:

| Surface | Flutter | Source |
|---|---|---|
| Local dev machine | **3.38.9** (rev `67323de285`, 2026-01-28, Dart 3.10.8) | `flutter --version` |
| `ci.yml` flutter-test | **3.41.7** | `.github/workflows/ci.yml:315` |
| `mobile-builds.yml` | **3.41.7** | `.github/workflows/mobile-builds.yml:42` |

Local has been ~6 months and three minor versions behind everything else. That
means every local test run has been exercising a different framework than the
one that gates merges and builds the store artifacts.

## Acceptance criteria

- [ ] Local Flutter reports `3.41.7` on channel `stable`
      (`flutter --version`), matching `ci.yml:315` and `mobile-builds.yml:42`
      exactly. Record before/after revisions in the status log.
- [ ] `npx nx run app:test` (`flutter test`) passes locally on 3.41.7. Any
      newly-failing test is triaged in the status log as
      framework-behavior-change vs. latent-bug-now-surfaced — do not blanket
      `skip` to get green.
- [ ] `flutter analyze` in `app/` has no **new** errors versus the 3.38.9
      baseline (capture the baseline before upgrading; deprecation warnings
      introduced by the bump are acceptable and listed, not silently ignored).
- [ ] A local web build succeeds:
      `flutter build web --dart-define=API_BASE_URL=http://localhost:8000`.
- [ ] **The dwds question is answered either way**, with evidence pasted:
      re-run one e2e flow against a live stack
      (`npx nx run e2e:stack-up`, then `flutter drive --driver=test_driver/integration_test.dart
      --target=integration_test/01_app_launch_test.dart -d chrome
      --dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000`)
      and record whether the debug service attaches.
      - Attaches → `debug/debug-e2edwds` resolved; hand back to `bqa102` to
        re-run the E-2 eval and unblock PR #12.
      - Still fails → append the negative result to `debug/debug-e2edwds` and
        pivot that ticket to the Chrome-side arm of the bisect (pin a Chrome
        for Testing build matching the toolchain). Do **not** silently widen
        this ticket into a Chrome downgrade.
- [ ] `pubspec.yaml`'s `environment.sdk` constraint (`>=3.7.0 <4.0.0`) still
      holds against the Dart shipped with 3.41.7; bump it only if the upgrade
      actually requires it, and say so.
- [ ] `flutter pub get` produces no unresolvable constraints; if
      `pubspec.lock` moves, the diff is reviewed rather than accepted blind.

## Technical notes

- **The local Flutter install is a git checkout** at
  `/Users/leonidbelyi/personal/flutter`, currently on branch `stable` at
  `67323de285b`. Upgrade via `flutter upgrade` (or
  `git checkout 3.41.7 && flutter precache`) — it is not a Homebrew or
  archive install, so don't reach for `brew`.
- **Rollback is cheap and should be stated in the status log before starting**:
  `git -C /Users/leonidbelyi/personal/flutter checkout 67323de285b && flutter precache`.
  Record the pre-upgrade revision so rollback is mechanical.
- **Do not change the CI pins in this ticket.** CI is already at 3.41.7 and is
  the target, not the thing being moved. If 3.41.7 turns out to be too old to
  drive Chrome 150, moving CI to a newer stable is a separate decision with
  real blast radius (flutter-test, mobile-builds, Play/App Store artifacts) —
  file it, don't fold it in.
- **Related drift worth noting, out of scope here**: `deploy-web` in
  `ci.yml:467-469` requests only `channel: stable` with *no* version pin, while
  `flutter-test` pins 3.41.7 — so the deployed web bundle can be built by a
  different framework than the one tested. Flagged in
  `_devx/workstreams/rotation-self-heal/decisions/2026-07-27-design-verify.md`.
  Leave it alone here; it deserves its own ticket.
- Prior art for the CI standardization is
  `_bmad-output/implementation-artifacts/ach-1-unify-flutter-channel-version-across-workflows.md`
  — it explains why the pin is `3.41.7` **stable** rather than the original
  `3.41.7-0.3.pre` master pin. Keep that decision intact.
- Expect churn in generated/analyzer output rather than app logic across a
  3.38 → 3.41 stable bump; the risk concentrates in `flutter test` and
  `flutter analyze`, which is why both are ACs.
- Blast radius is the whole Flutter app, so this is worth its own PR even
  though the diff may be tiny (possibly zero tracked files — the change is to
  the toolchain, with the repo evidence living in the status log and any
  `pubspec.lock` movement).

## Status log
- 2026-07-30T09:00 — filed from `debug/debug-e2edwds` triage during bqa102
  Phase 5. Local 3.38.9 vs CI 3.41.7 drift discovered while ruling out causes
  for the dwds attach failure (chromedriver version and Chrome first-run
  interstitials already eliminated by experiment; see the debug spec).
- 2026-07-30T10:34:46-06:00 — claimed by /devx in session /devx-2026-07-30T1034-61063
