---
hash: fltup1
type: dev
created: 2026-07-30T09:00:00-06:00
title: Upgrade local Flutter toolchain to the repo's pinned stable (3.41.7)
from: debug/debug-e2edwds-2026-07-27T19:00-dwds-chrome150-attach-failure.md
spawned:
  - debug/debug-e2egetit-2026-07-30T13:00-clientlatencyingest-not-registered-in-e2e-mode.md
  - debug/debug-nxappproj-2026-07-30T13:05-flutter-app-not-registered-with-nx.md
status: done
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

- [x] Local Flutter reports `3.41.7` on channel `stable`
      (`flutter --version`), matching `ci.yml:315` and `mobile-builds.yml:42`
      exactly. Record before/after revisions in the status log.
- [x] `npx nx run app:test` (`flutter test`) passes locally on 3.41.7. Any
      newly-failing test is triaged in the status log as
      framework-behavior-change vs. latent-bug-now-surfaced — do not blanket
      `skip` to get green.
      — **1564 passed / 0 failed**, same as the 3.38.9 baseline. Satisfied via
      `flutter test` in `app/` (this AC's own parenthetical): the `npx nx`
      form does not exist in this repo — there is no `app` nx project — so it
      exits 1 with `Cannot find project 'app'` without running anything.
      Discrepancy filed as `debug/debug-nxappproj`, not silently substituted.
      The 94 first-run failures were triaged to a stale 3.38.9 shader
      artifact and cleared by `flutter clean`; nothing was skipped.
- [x] `flutter analyze` in `app/` has no **new** errors versus the 3.38.9
      baseline (capture the baseline before upgrading; deprecation warnings
      introduced by the bump are acceptable and listed, not silently ignored).
- [x] A local web build succeeds:
      `flutter build web --dart-define=API_BASE_URL=http://localhost:8000`.
- [x] **The dwds question is answered either way**, with evidence pasted:
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
- [x] `pubspec.yaml`'s `environment.sdk` constraint (`>=3.7.0 <4.0.0`) still
      holds against the Dart shipped with 3.41.7; bump it only if the upgrade
      actually requires it, and say so.
- [x] `flutter pub get` produces no unresolvable constraints; if
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
- phase 2: spec ACs direct (v2 native); 7 ACs; workstream=none; red-artifacts=none

### Pre-upgrade state + rollback (recorded before touching the toolchain)

**Before:** `Flutter 3.38.9 • channel stable`, framework revision
`67323de285b00232883f53b84095eb72be97d35c` (2026-01-28), Dart 3.10.8,
DevTools 2.51.1. Install is a git checkout at
`/Users/leonidbelyi/personal/flutter`, on branch `stable`, working tree
clean, HEAD exactly at tag `3.38.9`.

**Rollback (mechanical, one command):**

```bash
git -C /Users/leonidbelyi/personal/flutter checkout stable \
  && git -C /Users/leonidbelyi/personal/flutter reset --hard 3.38.9 \
  && flutter precache
```

Safe because the pre-upgrade commit is pinned by the local tag `3.38.9` —
it cannot be lost to gc regardless of what the branch ref does.

**Upgrade route — `flutter upgrade` is the wrong tool here.** `flutter
upgrade` fast-forwards to the *tip* of the channel, and `origin/stable` is
now at **3.44.8** (`058e0af2c2b`), three minor versions past the CI pin.
Running it would overshoot 3.41.7 and re-create the drift this ticket
exists to close. Route taken instead: `git checkout stable && git reset
--hard 3.41.7` (tag `3.41.7` = `cc0734ac716`), which lands the exact pinned
version while keeping the branch name `stable` so `flutter --version` still
reports `channel stable` (Flutter derives channel from the branch name, so
a detached-HEAD `git checkout 3.41.7` would report an unknown channel and
fail AC #1).

The local `stable` branch reads `ahead 76, behind 2835` of `origin/stable`.
Verified benign before resetting: all 76 commits are upstream release/CP
commits (authors are Flutter team + `flutteractionsbot`) — Flutter rebuilds
the stable branch each release, so the divergence is upstream history
rewriting, not local customization. Nothing local is discarded by the reset.

**Baseline captured on 3.38.9 before the bump** (worktree
`.worktrees/dev-fltup1`, so it is the same tree the post-upgrade run uses):
- `flutter pub get` → clean; **`pubspec.lock` did not move** on 3.38.9.
- `flutter analyze` → **146 issues: 0 error, 76 warning, 70 info**
  (exit 1 — `flutter analyze` exits non-zero on any issue; the zero-error
  count is the meaningful figure and is the comparison basis for AC #3).
- `flutter test` → **1564 passed, 0 failed**, exit 0, 1m27s.

### Upgrade result

**After:** `Flutter 3.41.7 • channel stable`, framework revision
`cc0734ac71` (2026-04-15), engine `59aa584fdf`, **Dart 3.11.5**,
DevTools 2.54.2. Matches `ci.yml:315` and `mobile-builds.yml:42` exactly.
**AC #1 met.**

**AC #6 — `environment.sdk` needs no change.** Constraint is
`>=3.7.0 <4.0.0`; the shipped Dart moved 3.10.8 → 3.11.5, still inside the
range. Left untouched, as the AC prefers.

**AC #7 — `pubspec.lock` moved; diff reviewed, not accepted blind.** Six
packages, all `dependency: transitive`, all SDK-pinned (the versions
`flutter`/`flutter_test` force):

| Package | 3.38.9 | 3.41.7 |
|---|---|---|
| `characters` | 1.4.0 | 1.4.1 |
| `matcher` | 0.12.17 | 0.12.19 |
| `material_color_utilities` | 0.11.1 | 0.13.0 |
| `test` | 1.26.3 | 1.30.0 |
| `test_api` | 0.7.7 | 0.7.10 |
| `test_core` | 0.6.12 | 0.6.16 |

No direct dependency moved and no constraint was edited — this is the SDK
pin propagating, which is exactly the churn the ticket predicted. Worth
knowing for later: `material_color_utilities` 0.11.1 → 0.13.0 is the only
one that can change *rendered output* (Material 3 tonal-palette
derivation); the full suite passing post-clean says nothing user-visible
shifted, but it is the package to suspect first if theme colors ever drift.

**AC #3 — no new analyze errors, and in fact zero new issues of any
severity.** Compared as a *set diff* of normalized issue lines, not by
count (counts can hide offsetting changes):

| | 3.38.9 | 3.41.7 |
|---|---|---|
| error | 0 | **0** |
| warning | 76 | 76 |
| info | 70 | 64 |
| total | 146 | 140 |

`comm -13` (new-on-3.41.7) is **empty** — the bump introduced no new
diagnostics at all, deprecation warnings included. The six that
*disappeared* are all `deprecated_member_use_from_same_package`. Both runs
exit 1 because `flutter analyze` exits non-zero on any issue; the
error count is the meaningful figure and it is 0 → 0.

**AC #2 — suite green on 3.41.7, but only after `flutter clean`. Triage
below; nothing was skipped.** First post-upgrade run: **1470 passed, 94
failed**. All 94 failures shared one signature, byte-identical:

```
Exception: Asset 'shaders/ink_sparkle.frag' manifest could not be decoded:
INVALID_ARGUMENT: Unsupported runtime stages format version. Expected 1, got 0.
  #0  new FragmentProgram._fromAsset (dart:ui/painting.dart:5337:7)
```

Triage verdict: **neither framework-behavior-change nor latent-bug-surfaced
— stale build artifact.** "Expected 1, got 0" is the 3.41.7 engine reading
an `ink_sparkle.frag` shader *compiled by the 3.38.9 engine* and left in
`app/build` + `app/.dart_tool` by the baseline run. Every one of the 94 is a
widget test that pumps a Material ink ripple; the 1470 that passed are the
ones that never rasterize a splash. Confirmed by experiment rather than
asserted: `flutter clean && flutter pub get && flutter test` →
**1564 passed, 0 failed, exit 0, zero residual `ink_sparkle` errors** —
exactly the baseline number. Same tree, same code, only the stale artifact
removed. 94 + 1470 = 1564, so no test silently vanished.

**Gotcha worth keeping: `flutter clean` is mandatory after an in-place SDK
bump.** CI never hits this (it builds from a clean checkout), so it is a
local-upgrade-only trap — and it presents as 94 unrelated-looking widget
failures, which is exactly the shape that tempts a blanket `skip`.

**AC #4 — web build succeeds.** `flutter build web
--dart-define=API_BASE_URL=http://localhost:8000` → exit 0, `✓ Built
build/web`, 43.2s compile. Icon tree-shaking behaved normally
(MaterialIcons 98.0%, CupertinoIcons 99.4%).

### AC #5 — the dwds question: **ANSWERED, POSITIVE. dwds now attaches.**

Setup: canonical stack via `npx nx run e2e:stack-up` (API healthy at
`GET /v1/health` → `{"status":"ok"}`), chromedriver **150.0.7871.182**
matched to local Chrome **150.0.7871.187**, then flow 01 exactly as the
debug spec's repro prescribes. Hard-bounded at 420s so it could not wedge
the way the three abandoned loop iterations did.

Result — the blocking symptom is **gone**:

```
Launching integration_test/01_app_launch_test.dart on Chrome in debug mode...
Waiting for connection from debug service on Chrome...             25.5s
Debug service listening on ws://127.0.0.1:50013/fKozVNQEnc0=/ws
```

`grep -c AppConnectionException` over the full run → **0**. On 3.38.9 this
step failed every time at ~19–21s inside
`DevHandler._startLocalDebugService`. On 3.41.7 it connects at 25.5s and
the test body **executes**. That confirms the debug spec's leading
hypothesis: the failure was Flutter-toolchain ↔ Chrome-150 version skew,
and moving local to the CI pin resolves it. Per AC #5 this routes to the
"attaches" arm — **no Chrome downgrade, and the CI pins stay put.**

**The flow still does not pass, for an unrelated reason downstream of the
attach.** Being explicit so this is not misread as "e2e is green":

```
Bad state: GetIt: Object/factory with type ClientLatencyIngest is not
registered inside GetIt.
  package:palateful/core/router/app_router.dart 98:32
  package:palateful/core/services/perf_navigator_observer.dart 87:25
```

That StateError throws in a scheduler callback during the first frame, so
the router never finishes building and the follow-on
`Expected: at least one matching candidate / Found 0 widgets with text
"Home"` is its consequence, not a second defect. One root cause, a DI
registration gap under `E2E_MODE=true`. Filed separately as
`debug/debug-e2egetit` rather than folded in here — it is app/DI code, not
toolchain, and widening this ticket into it is exactly what the
"do not silently widen" note forbids.

(`DRIVE_EXIT=137` is my own 420s watchdog SIGKILL-ing a `flutter drive`
that hung *after* the suite had already reported `00:20 +1 -1: Some tests
failed`. The verdict was in before the kill; 137 is not the test result.)

### Out-of-scope defects filed, not fixed here

- `debug/debug-e2egetit` — the `ClientLatencyIngest` GetIt gap above; the
  new blocker for bqa102's E-2 eval.
- `debug/debug-nxappproj` — **AC #2 names `npx nx run app:test`, which does
  not exist.** `npx nx show projects` lists 11 projects and `app` is not one
  of them; there is no `app/project.json` anywhere in the repo, so the
  command exits 1 with `Cannot find project 'app'` from any directory. The
  gate was therefore run as `flutter test` in `app/` — which is what the
  AC's own parenthetical says, and what `devx.config.yaml → projects[app]`
  declares. Recording rather than quietly substituting, since CLAUDE.md
  mandates nx-first and the Flutter app is the one surface not wired in.

### Environment obstacles cleared (recorded so the next run doesn't re-debug)

`npx nx run e2e:stack-up` failed three times before succeeding; none of it
was caused by the upgrade:

1. `Conflict. The container name "/palateful-migrator" is already in use` —
   two one-shot migrator containers, both `Exited (0)`, left over from the
   2026-07-28 abandoned e2edwds loop run. Removed.
2. `Bind for 0.0.0.0:4566 failed: port is already allocated` — an **entire
   orphaned stack** from that same dead run was still up after 2 days under
   compose project `debug-e2edwds`, holding 8000/5432/4566/4040. Its
   worktree no longer exists (`git worktree list` has no e2edwds entry) and
   its API answered `000` on every path — bound but wedged. Stopped it
   (`docker compose -p debug-e2edwds stop`; containers only, volumes left
   intact).
3. `could not translate host name "db"` — the half-created containers from
   attempts 1–2 were stranded off `palateful_default`. Fixed with a plain
   `docker compose ... down` (no `-v`, so no volume data destroyed) then a
   clean `up`, which went green.

Worth knowing: an abandoned loop item can leave a live port-holding docker
stack behind indefinitely. The loop's worktree cleanup does not tear down
compose projects.

### Phase 4 / Phase 5

- phase 4: single-pass adversarial review (diff is 4 files / ~282 lines and
  almost entirely markdown + a generated lockfile — below the >500-line
  multi-agent threshold); 5 findings, ALL fixed in-place. Most load-bearing:
  the run was about to leave its own 5-container e2e stack up indefinitely
  — the exact orphan-stack failure this ticket had just spent three
  stack-up attempts cleaning up after — so the stack is now torn down
  (`docker compose ... down`, volumes preserved) as part of the run. Others:
  (a) AC #2 was marked with a non-conventional `[~]` checkbox, corrected to
  `[x]` with the nx discrepancy annotated inline rather than invented as a
  new convention; (b) `spawned:` frontmatter was missing, so the two filed
  debug specs were reachable only by prose — added; (c) `debug-e2edwds` AC #3
  was at risk of being ticked `[x]` on a "resolved" ticket when the E-2 eval
  is *not* green — set to `[-]` (blocked) with the successor named, since
  marking it done would have misreported e2e as working; (d) the
  `@puppeteer/browsers` install dropped an untracked 16MB `chromedriver/`
  tree in the repo root — relocated to the scratchpad so it cannot be
  committed. Re-review of the changed hunks clean.
- phase 5: touched surface = `app/pubspec.lock` (project `app`) + 4 markdown
  backlog/spec files. Gate for `app` per `devx.config.yaml` is `flutter test`
  → **1564 passed, 0 failed, exit 0**, run *after* `flutter clean` and after
  the lockfile reached its final state, so the green is against exactly what
  is being committed. `flutter analyze` → 0 errors, no new diagnostics vs
  baseline. `flutter build web` → exit 0. No Python/Node project was touched,
  so no other project's gates apply. Coverage is informational under YOLO and
  is not a merge blocker.
- phase 7: CI success — devx-ci (run 30564663961) and CI & Deploy (run
  30564663979), both terminal at the branch tip. Tour built + published:
  https://htmlpreview.github.io/?https://raw.githubusercontent.com/LeoTheMighty/palateful/devx-tours/tours/fltup1/tour.html
- phase 8: check-hold `{"hold":false}`; `devx merge-gate fltup1` →
  `{"merge":true}` (exit 0). merged via PR #17 (squash → ff3eddcb).
  `gh pr merge` printed `fatal: 'main' is already used by worktree` and the
  merge still landed — the known in-worktree artifact; `gh pr view` reporting
  `state: MERGED` with `mergeCommit ff3eddcb` is what was trusted.
