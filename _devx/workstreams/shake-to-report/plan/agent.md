# Plan — Shake To Report

<!-- Stage: Plan. Gate: `devx gate coverage f89791` (plan mode — one row per
     E-id; P0 floor: every P0 expectation `full` and naming a runnable
     artifact). Sizing rule: a phase is one cohesive concern with a
     verifiable exit, sized to land as a single reviewable PR. Default to
     more, smaller phases. One phase ≙ one dev spec ≙ one PR. -->

<!-- Phase order follows design § Migration plan: server first (a client
     that sends `trigger` early loses feedback), the native dependency on
     its own (no PR-time CI builds iOS or Android), the host behind ring
     `admins`, then controls, then the admin route once arq103 is on main.
     Critique skipped: thoroughness send-it, and the authoring session has
     no subagent tool for the lenses. -->

## Current state

- No motion sensing anywhere in the app, and no sensor plugin in
  `app/pubspec.yaml`.
- The feedback sheet opens only from Profile
  (`app/lib/features/profile/profile_screen.dart:156`), with a hard-coded
  route, and its offline queue flushes only while Profile is mounted
  (`:65`, `:77`).
- The feedback context rejects unknown keys
  (`services/api/src/api/v1/user/create_user_feedback.py:69-82`).
- `GET /v1/flags/perf` serves two latency flags
  (`services/api/src/api/v1/flags/get_perf_flags.py:28`); nothing in
  terraform sets them.
- The dev-request form exists on `feat/dev-arq103` (`b9bf7104`), not on
  `main`.

## Desired state

- On an iOS or Android phone, a deliberate shake on any screen shows a
  prompt; a tap opens the dev-request form for an admin and the feedback
  sheet for everyone else, over the screen the user was on.
- Everyday motion, typing, open dialogs and already-open forms produce
  nothing.
- Leo controls who sees it with a terraform variable; a user can turn it
  off in Profile.
- The four P0 evals run in CI's Flutter job from the phase that turns
  each green, so they keep looking after this workstream closes.

## What we're NOT doing

- Any edit to arq103's screen, its route, or anything else in
  `admin-request-intake`'s plan files.
- Web motion, screenshot or log attachments, prompt telemetry.
- An Android toolchain upgrade or sensors_plus ≥ 7.
- A version bump. That is Leo's call (Phase 3, Risks).

## Risks

**Riskiest phase: Phase 3.** It adds a native plugin, and nothing at PR
time builds iOS or Android: CI's Flutter job runs `flutter analyze`,
`flutter test` and `flutter build web` only (`.github/workflows/ci.yml:419`,
`:447`, `:528`); Android builds on a `v*.*.*` tag
(`.github/workflows/mobile-builds.yml`), iOS on Xcode Cloud. So a plugin
that breaks either build, or an iOS app that crashes for a missing
`Info.plist` key, would show up at release time, not in review. And the
phase edits `app/pubspec.yaml`, which by itself fires Xcode Cloud on
`main` (`docs/DEPLOYMENT.md:96-111`).

**What this order exposes.** Phase 4 turns listening on for admins in
production (ring `admins`) while they still get the feedback sheet, until
Phase 6. That is the dogfood period, on purpose. Phase 2 sends `trigger`
from Profile, so Phase 1 must be deployed first; since the merge is the
deploy and app releases lag the server, the order holds as long as Phase 1
is not reverted after a client release carries Phase 2.

**Client phases cannot be rolled back on phones by a revert.** A revert
fixes `main`, not installed apps. Phases 4–6 have a field rollback (ring
`off`); Phases 2 and 3 do not, so they are held to "behaves as before".

| Risk | Phase | Blast radius | Rollback |
|---|---|---|---|
| sensors_plus breaks the iOS or Android build, unseen until release | 3 | med — the next release | Phase 3's exit requires local `flutter build apk --debug` and `flutter build ios --simulator --no-codesign` to pass and be recorded; revert before any tag |
| `Info.plist` key missing, app crashes on first motion read | 3 | high — every iOS user of that release | Key lands in the same commit as the dependency; nothing reads motion until Phase 4, and only for admins |
| The pubspec edit fires Xcode Cloud with no version bump: one failed run (duplicate build number) | 3 | low — a red Xcode Cloud status | Expected and harmless; or Leo bumps the version and it becomes a release. Recorded in the PR body |
| `trigger` removed from the server after a client release sends it: feedback 422s and re-queues forever | 1 | high — silent loss | One-way once a release carries Phase 2: roll back by shipping a client without `trigger` first, then the server |
| The moved flush loop trips `tools/no-silent-catch-check.sh` (it covers `app/lib/features/**/services/`) | 2 | low — CI red | Its catches report through `ErrorReporter.report`, which the guard accepts |
| FR-3's thresholds miss real shakes or fire in pockets | 4 | low — admins only while ring is `admins` | Retune `ShakeTuning` through E-7; E-2's traces move with it; ring `off` in the meantime |
| The new CI eval step is slow or flaky and reddens every PR | 4, 6 | med — shared gate | The harness exits 3 for its own breakage, distinct from RED (1); a flaky harness is a `devx revise`, never a softened assertion |
| arq103 never reaches `main`, or changes its path | 6 | low — admins keep getting feedback | Phase 6 waits; the route-exists check keeps admins on the user path; a path change is a `devx revise` |
| The everyone-rollout waits on Phase 6 and so on admin-request-intake's bridge | 6 | low — schedule | Leo may run E-7 without its admin step and widen the ring after Phase 5; recorded as his call |

## Expectation coverage

| E-id | Priority | Verified in phase | Validation type | Eval artifact | Coverage |
|---|---|---|---|---|---|
| E-1 | P0 | 4 | tests-first | `_devx/workstreams/shake-to-report/evals/E-1_user_path.sh` | full |
| E-2 | P0 | 4 | tests-first | `_devx/workstreams/shake-to-report/evals/E-2_everyday_motion.sh` | full |
| E-3 | P0 | 4 | tests-first | `_devx/workstreams/shake-to-report/evals/E-3_no_interruption.sh` | full |
| E-4 | P0 | 6 | tests-first | `_devx/workstreams/shake-to-report/evals/E-4_role_and_ring.sh` | full |
| E-5 | P1 | 4 | tests-after | `app/test/core/shake/shake_eligibility_test.dart` | full |
| E-6 | P1 | 1 | tests-after | `services/api/tests/test_shake_flags_and_trigger.py` | full |
| E-7 | P1 | 6 | human | `_devx/workstreams/shake-to-report/evals/E-7_device_protocol.md` | full |
| E-8 | P1 | 2 | tests-after | `app/test/features/profile/feedback_launcher_test.dart` | full |
| E-9 | P2 | 5 | tests-after | `app/test/features/profile/shake_settings_test.dart` | full |
| E-10 | P1 | 6 | tests-after | `app/test/features/profile/non_shake_paths_test.dart` | full |

E-4's ring cases (`off`, `admins` for a non-admin, no flags answer) can
pass from Phase 4; its admin case needs Phase 6 and arq103 on `main`, so
the whole eval is listed at Phase 6. E-10's dev-request half needs arq103's
dashboard tile, so it is listed there too.

## Phase checklist

- [ ] Phase 1: Server accepts the trigger and serves the ring (dev spec: shk101)
- [ ] Phase 2: One feedback launcher with an app-wide flush (dev spec: shk102)
- [ ] Phase 3: Motion dependency and the shake recognizer (dev spec: shk103)
- [ ] Phase 4: Shake host — prompt, suppression, feedback for every admitted user (dev spec: shk104)
- [ ] Phase 5: Device switch and discoverability hint (dev spec: shk105)
- [ ] Phase 6: Admins get the dev-request form (dev spec: shk106)

**External gates:**

- **X-1 — arq103's route on `main`** (`admin-request-intake` phase 3, PR
  #132 into `feat/admin-request-slice`, held there for that workstream's
  own bridge gate). Needs `/admin/dev-requests/new` registered on
  `origin/main` with `AdminDevRequestNewScreen.routePath` and pop-to-pusher
  close. **Phase 6 merges only after X-1.** Verified on the branch at
  `b9bf7104` (design RQ12); not on `main` as of this plan.
- **X-2 — the release that carries the client phases** (Leo). Phases 2–6
  reach phones only in a version-bumped release (iOS via Xcode Cloud, Android
  via a `v*.*.*` tag). E-7 runs on that release's builds.

After Phase 6: Leo runs E-7, then edits the ring in
`terraform/environments/prod/main.tf` to `everyone`. That is an ops step,
not a phase.

## Execution graph

```yaml
phases:
  - { id: 1, depends_on: [] }
  - { id: 2, depends_on: [1] }
  - { id: 3, depends_on: [], parallel_safe: true }
  - { id: 4, depends_on: [2, 3] }
  - { id: 5, depends_on: [4] }
  - { id: 6, depends_on: [5] }
waivers: []
```

## Phases

### 1. Phase: Server accepts the trigger and serves the ring

**Overview**: The two server-side contracts every later phase leans on:
`trigger` in the feedback context, and `shake_report` on the flags
endpoint, with its terraform variable. First, because the merge is the
deploy and Phase 2's client sends `trigger`.

**Files**:
- `services/api/src/config.py` — `shake_report_ring: Literal["off", "admins", "everyone"] = "admins"`.
- `services/api/src/api/v1/flags/get_perf_flags.py` — `shake_report` on the response; docstring says it is a product flag on a perf-named endpoint.
- `services/api/src/api/v1/user/create_user_feedback.py` — `trigger: Literal["profile", "shake"] | None` on `FeedbackContext`.
- `services/api/tests/test_shake_flags_and_trigger.py` — new (E-6).
- `terraform/modules/ecs/main.tf` — `variable "shake_report_ring"` (default `admins`) and `SHAKE_REPORT_RING` in the API container's environment.
- `terraform/environments/prod/main.tf` — pass `shake_report_ring = "admins"` to `module "ecs"`.
- `docs/PERFORMANCE_OPS.md` — the ring, how to change it, and that a console flip lasts only until the next terraform-managed revision (this also applies to the existing latency switch).

**Context**:
- PRD FR-10, FR-13; design § Rollout ring and switch, § Interfaces.
- `services/api` is pinned at 100% coverage; run targeted tests through
  `tools/api-pytest-targeted.py`.
- Terraform: local CLI 1.4.2 vs state's 1.16.3 invents phantom diffs
  (`project_terraform_version_skew`); read a plan from CI, not locally.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - `python3 tools/api-pytest-targeted.py tests/test_shake_flags_and_trigger.py` (from `services/api`) exits 0.
  - `npx nx run api:test` green at 100%; `npx nx run api:lint` clean.
  - CI's terraform plan for prod shows one added environment entry on the API task definition and nothing else.

**Tasks**:
- [ ] T1.1 Setting and flags field — files: `services/api/src/config.py`, `services/api/src/api/v1/flags/get_perf_flags.py`
- [ ] T1.2 Trigger on the feedback context — files: `services/api/src/api/v1/user/create_user_feedback.py`
- [ ] T1.3 Tests (E-6) — files: `services/api/tests/test_shake_flags_and_trigger.py`
- [ ] T1.4 Terraform variable and env entry — files: `terraform/modules/ecs/main.tf`, `terraform/environments/prod/main.tf`
- [ ] T1.5 Runbook — files: `docs/PERFORMANCE_OPS.md`

### 2. Phase: One feedback launcher with an app-wide flush

**Overview**: Move Profile's sheet opener and offline flush into one
launcher that takes a route and a trigger, and flush at startup and on
every resume from the app root. Profile looks and behaves as before.

**Files**:
- `app/lib/features/profile/services/feedback_launcher.dart` — new: `open(context, trigger:, route:)`, `flushQueue()`.
- `app/lib/features/profile/widgets/feedback_sheet.dart` — `trigger` parameter added to the context.
- `app/lib/features/profile/profile_screen.dart` — the tile and its flush calls go through the launcher; `_openFeedbackSheet`, `_flushFeedbackQueue`, `_captureFeedbackContext` removed.
- `app/lib/main.dart` — `PalatefulApp` calls `flushQueue()` once signed in at startup, and on resume (`:439`).
- `app/test/features/profile/feedback_launcher_test.dart` — new (E-8).

**Context**:
- PRD FR-9; design § Feedback launcher. Phase 1 must be deployed.
- Platform: `web` when `kIsWeb`, else from `defaultTargetPlatform`; never
  `dart:io` (design § Feedback launcher).
- `tools/no-silent-catch-check.sh` covers `app/lib/features/**/services/`:
  the moved catches call `ErrorReporter.report`.
- Existing `app/test/features/profile/feedback_sheet_test.dart` stays green
  unchanged.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - `flutter test test/features/profile/feedback_launcher_test.dart test/features/profile/feedback_sheet_test.dart` passes in `app/`.
  - `flutter analyze` clean; `bash tools/no-silent-catch-check.sh` exits 0.

**Tasks**:
- [ ] T2.1 Launcher — files: `app/lib/features/profile/services/feedback_launcher.dart`
- [ ] T2.2 Sheet trigger — files: `app/lib/features/profile/widgets/feedback_sheet.dart`
- [ ] T2.3 Profile uses the launcher — files: `app/lib/features/profile/profile_screen.dart`
- [ ] T2.4 App-root flush — files: `app/lib/main.dart`
- [ ] T2.5 Tests (E-8) — files: `app/test/features/profile/feedback_launcher_test.dart`

### 3. Phase: Motion dependency and the shake recognizer

**Overview**: sensors_plus 6.1.x and its `Info.plist` key, the one adapter
that imports it, and the pure-Dart recognizer, unit-tested with
synthesized traces. Nothing subscribes yet. On its own so that a native
build break is attributable to it alone.

**Files**:
- `app/pubspec.yaml` — `sensors_plus: ">=6.1.1 <7.0.0"`.
- `app/pubspec.lock` — resolved.
- `app/ios/Podfile.lock` — the plugin's pod.
- `app/ios/Runner/Info.plist` — `NSMotionUsageDescription`.
- `app/lib/core/shake/motion_source.dart` — new: the only sensors_plus import; `userAccelerometerEventStream(samplingPeriod: SensorInterval.gameInterval)` → `MotionSample`; errors end the stream after one breadcrumb.
- `app/lib/core/shake/shake_recognizer.dart` — new: `ShakeTuning`, `MotionSample`, `ShakeRecognizer` (design § Recognizer, steps 1–5).
- `app/test/core/shake/shake_recognizer_test.dart` — new: the E-2 trace shapes plus boundary cases at each `ShakeTuning` edge.

**Context**:
- PRD FR-2, FR-3, FR-4 (cooldown); design § Recognizer and its failure
  handling.
- `app/pubspec.yaml` on `main` fires Xcode Cloud. Do not bump the version;
  say in the PR body that one failed Xcode Cloud run is expected unless
  Leo bumps it.
- `app/lib/core/**` is under the silent-catch ratchet
  (`tools/silent-catch-core-baseline.txt`): no new swallowing catch.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - `flutter test test/core/shake/shake_recognizer_test.dart` passes.
  - `flutter analyze` clean; `flutter build web --release` succeeds.
  - `flutter build apk --debug` and `flutter build ios --simulator --no-codesign` both succeed locally; their last lines are pasted in the PR body (no PR-time CI builds either).

**Tasks**:
- [ ] T3.1 Dependency, lockfiles, Info.plist key — files: `app/pubspec.yaml`, `app/pubspec.lock`, `app/ios/Podfile.lock`, `app/ios/Runner/Info.plist`
- [ ] T3.2 Motion adapter — files: `app/lib/core/shake/motion_source.dart`
- [ ] T3.3 Recognizer and tuning — files: `app/lib/core/shake/shake_recognizer.dart`
- [ ] T3.4 Trace tests — files: `app/test/core/shake/shake_recognizer_test.dart`
- [ ] T3.5 Local iOS and Android builds, recorded in the PR

### 4. Phase: Shake host — prompt, suppression, feedback for every admitted user

**Overview**: The host above the router, the modal-route observer on every
navigator, the ring on the client, and the prompt. Every admitted user,
admins included, is routed to feedback; the ring stays `admins`, so this
is the dogfood build. Turns E-1, E-2 and E-3 green and starts running them
in CI.

**Files**:
- `app/lib/core/shake/shake_host.dart` — new: eligibility, subscription lifecycle, suppression, prompt, feedback routing, cooldown and mute.
- `app/lib/core/shake/modal_route_tracker.dart` — new: `PopupRoute`-on-top per navigator.
- `app/lib/core/services/perf_flags_service.dart` — parse `shake_report`, keep the last value in SharedPreferences, `shakeRing`, notify on change.
- `app/lib/core/router/app_router.dart` — the tracker on the root observer list (`:248`) and each branch's (`:731`, `:765`, `:783`, `:820`, `:842`).
- `app/lib/main.dart` — `scaffoldMessengerKey` on `MaterialApp.router`; `ShakeHost` around the builder's child (`:562`).
- `app/test/core/shake/shake_eligibility_test.dart` — new (E-5).
- `.github/workflows/ci.yml` — in the Flutter job, after `flutter test`, run `bash _devx/workstreams/run-eval.sh shake-to-report/evals/E-1_user_path.sh` and the same for E-2 and E-3, from `_devx/workstreams`.

**Context**:
- PRD FR-1, FR-4…FR-8; design § Host, § Modal-route tracking, § Rollout
  ring and switch (client).
- The P0 evals are locked (`gate_status.red_eval_shas`). Make the code
  pass them; a genuinely wrong eval is `devx revise`, not an edit.
  `devx gate evals f89791 --verify` must stay PASS.
- Prompt copy is fixed by FR-5 and the evals find it by text.
- Use `defaultTargetPlatform`, never `dart:io` `Platform`.
- `Info.plist` key from Phase 3 is what keeps the first real motion read
  from crashing.

**Verification plan**:
- Type: tests-first
- Success criteria:
  - `bash _devx/workstreams/run-eval.sh shake-to-report/evals/E-1_user_path.sh` (from `_devx/workstreams`) exits 0; likewise E-2 and E-3.
  - `flutter test test/core/shake/shake_eligibility_test.dart` passes; the whole `flutter test` suite passes.
  - CI's Flutter job runs the three evals and is green.

**Tasks**:
- [ ] T4.1 Client ring — files: `app/lib/core/services/perf_flags_service.dart`
- [ ] T4.2 Modal-route tracker on every navigator — files: `app/lib/core/shake/modal_route_tracker.dart`, `app/lib/core/router/app_router.dart`
- [ ] T4.3 Host and prompt — files: `app/lib/core/shake/shake_host.dart`, `app/lib/main.dart`
- [ ] T4.4 Eligibility tests (E-5) — files: `app/test/core/shake/shake_eligibility_test.dart`
- [ ] T4.5 Turn E-1, E-2, E-3 green; add them to CI — files: `.github/workflows/ci.yml`

### 5. Phase: Device switch and discoverability hint

**Overview**: `Shake to report` in Profile's settings, remembered on the
device, and the Send Feedback subtitle hint for eligible non-admins.

**Files**:
- `app/lib/core/shake/shake_settings.dart` — new: SharedPreferences-backed switch (`shake_report_enabled`, default on), in the `theme_mode_provider.dart` pattern.
- `app/lib/core/shake/shake_host.dart` — the switch becomes an eligibility input.
- `app/lib/features/profile/profile_screen.dart` — the switch row (iOS and Android only) and the FR-12 subtitle.
- `app/test/features/profile/shake_settings_test.dart` — new (E-9).

**Context**:
- PRD FR-11, FR-12; design § Rollout ring and switch.
- E-1…E-3 must stay green.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - `flutter test test/features/profile/shake_settings_test.dart` passes.
  - CI's Flutter job green, including the three evals.

**Tasks**:
- [ ] T5.1 Switch state — files: `app/lib/core/shake/shake_settings.dart`, `app/lib/core/shake/shake_host.dart`
- [ ] T5.2 Profile row and hint — files: `app/lib/features/profile/profile_screen.dart`
- [ ] T5.3 Tests (E-9) — files: `app/test/features/profile/shake_settings_test.dart`

### 6. Phase: Admins get the dev-request form

**Overview**: An admin at prompt and tap gets `File a dev request?` /
`Request` and the arq103 route, pushed on the root navigator; any doubt
keeps the user path. Turns E-4 green and adds it to CI; ends with the
device protocol. Merges only after X-1.

**Files**:
- `app/lib/core/shake/shake_host.dart` — admin copy, the twice-checked role, the route-exists check, `push(AdminDevRequestNewScreen.routePath)`.
- `app/test/features/profile/non_shake_paths_test.dart` — new (E-10).
- `.github/workflows/ci.yml` — add the E-4 eval run beside E-1…E-3.
- `_devx/workstreams/shake-to-report/evals/E-7_device_protocol.md` — the Runs table rows only (its writable section).

**Context**:
- PRD FR-7, FR-14; design § Host (routing on tap).
- Import the path from `AdminDevRequestNewScreen`; never copy the string.
- The router's `/admin` redirect and the server's `require_admin_async`
  stay the authority; the host's check is routing only.

**Verification plan**:
- Type: tests-first, then human
- Success criteria:
  - `bash _devx/workstreams/run-eval.sh shake-to-report/evals/E-4_role_and_ring.sh` exits 0; E-1…E-3 still exit 0.
  - `flutter test test/features/profile/non_shake_paths_test.dart` passes.
  - E-7 run on release builds (X-2), its Runs table filled with one row per phone.

**Tasks**:
- [ ] T6.1 Admin routing — files: `app/lib/core/shake/shake_host.dart`
- [ ] T6.2 Non-shake path tests (E-10) — files: `app/test/features/profile/non_shake_paths_test.dart`
- [ ] T6.3 Turn E-4 green; add it to CI — files: `.github/workflows/ci.yml`
- [ ] T6.4 After X-2: run E-7 and record it — files: `_devx/workstreams/shake-to-report/evals/E-7_device_protocol.md`
