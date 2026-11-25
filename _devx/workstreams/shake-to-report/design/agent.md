# Design — Shake To Report

<!-- Stage: Design. Gate: `devx gate coverage f89791` (design mode — one
     tri-state row per G-/UC-/CAP-/FR- ID in prd/agent.md). Hard rule: don't
     plan here. No phases, no tasks — design is the approach, not the
     sequence. Citations are to palateful origin/main 8434722f unless they
     say otherwise; research answers are in design/research.md (RQn). -->

## Overview

- **Objective**: From any screen of the iOS or Android app, a deliberate
  shake offers the right form (the dev-request form for an admin, the
  feedback sheet for everyone else) and records where the user was, while
  everyday kitchen motion costs the user nothing and Leo can narrow or
  stop it without an app release.
- **Solution**: A pure-Dart recognizer reads gravity-removed acceleration
  through one thin adapter over sensors_plus 6.1. A host widget above the
  router owns eligibility, the subscription's lifecycle, suppression, a
  non-modal prompt and the routing on tap. Feedback opens through one
  launcher that Profile's tile also uses and that flushes the offline
  queue app-wide. The rollout ring rides the existing `/v1/flags/perf`
  fetch, set by a terraform variable; a device switch sits in Profile.

## Constraints

- **The Android toolchain is AGP 8.7.3, Gradle 8.12, Kotlin 2.1.0**
  (RQ8), so sensors_plus 7.x is out without a toolchain upgrade; 6.1.x is
  the line that fits (the `shake` package pins `^6.1.1` on the same
  plugin).
- **sensors_plus ≥ 6.0 crashes on iOS without `NSMotionUsageDescription`**
  (RQ8). The key lands in the same change as the dependency.
- **The feedback context rejects unknown keys** (RQ4) and the sheet queues
  on any error (RQ3), so the server must accept `trigger` before any
  client sends it.
- **`isAdmin` is set once per cold start and never persisted** (RQ2). It
  cannot be made fresher without a network call on the shake path.
- **Terraform owns the API task definition's environment** (RQ5), so a
  console flip is temporary; a durable ring change is a terraform change.
- **`main` carries a 100% coverage pin on `services/api`**, so the backend
  part ships with its tests (`project_api_coverage_100`).
- **CI builds web** (`.github/workflows/ci.yml:528`, `:628`): every new
  import must compile under dart2js, including a plugin with a web
  implementation the app never calls.
- **No Flutter RED registry exists.** A failing test under `app/test/`
  turns CI's `flutter test` red for everyone, so the P0 evals live outside
  the `app/` package (RQ13).

## Risks

- A shake trigger fires on everyday motion and annoys users → two-step
  trigger, FR-3's reversal shape, a 2-ignored-prompts mute, ring starts at
  `admins` → proven by E-2 and E-7.
- A shake takes over a screen mid-task (typing, timer, import) → the
  prompt takes no focus and navigates nowhere; suppression while busy;
  forms are pushed, never `go`ne → proven by E-3.
- An unknown or stale role sends a non-admin into the admin form, or the
  admin form becomes the fallback → admin only when `isAdmin` holds at
  prompt and tap; any other case is the user path; the server still
  refuses → proven by E-4.
- The native dependency breaks the iOS app (missing Info.plist key) or the
  Android build (toolchain) → pin 6.1.x, add the key with it, CI's iOS,
  Android and web builds, a fresh-install step on devices → proven by E-5
  and E-7.
- Feedback sent with `trigger` before the server knows the key is lost
  silently → server change deploys first → proven by E-6 and E-8.
- The off switch is undone by the next deploy → the ring is a terraform
  variable, not a console edit → proven by E-4 (ring `off`) and E-7.
- Continuous sampling drains battery → sampled only while resumed and
  eligible; cancelled on pause, sign-out, switch off → proven by E-5 and
  E-9 (subscription counts).
- The evals are coupled to sensors_plus's channel names → the plugin is
  pinned; a rename makes the harness's channel control fail, which reads
  as a broken eval, not as RED or GREEN → proven by the E-1…E-4 controls.

## Trade-offs

- **A prompt between shake and form, over opening the form directly.** A
  false trigger then costs a 4 s snackbar instead of a stolen screen. It
  costs a true trigger one tap.
- **A floating snackbar, over a dialog.** A dialog is modal: it takes focus
  and blocks the screen, which is the interruption this design exists to
  avoid.
- **Drop a shake while busy, over queueing it.** A queued gesture fires
  later, when the user has moved on: a surprise is worse than a miss.
- **Our own recognizer, over the `shake` package.** Its default fires on a
  single 2.7 g spike (RQ8), which is what a counter knock produces; we
  need alternating peaks. A pure-Dart recognizer is also testable with
  synthesized traces.
- **Gravity-removed acceleration, over raw.** The magnitude no longer
  depends on how the phone is held, and the free-fall bound (gait's
  downward half cannot exceed 1 g) applies directly.
- **sensors_plus 6.1, over 7.x.** 7.x forces an Android toolchain upgrade
  unrelated to this feature (RQ8).
- **Accelerometer on both platforms, over iOS's native shake event.** The
  native `motionEnded` event needs a platform channel, behaves differently
  on Android, and cannot be driven from a widget test.
- **The ring on `/v1/flags/perf`, over a new flags endpoint.** It reuses
  the fetch, timeout and 5-minute refresh the client already runs (RQ5).
  The cost is a product flag on a perf-named endpoint, recorded in its
  docstring.
- **A terraform variable, over a console flip.** Durable across deploys
  (RQ5); slower to change, so the console flip stays the emergency lever.
- **Last-received ring kept on the device, falling back to `admins`, over
  fail-open.** The existing perf flags fail open; a product rollout must
  not widen itself because a fetch failed.
- **A device switch in SharedPreferences, over a server-side preference.**
  No API change, and it is the device that shakes.
- **`isAdmin` at prompt and at tap, over a fresh `/me` call.** No network
  on the shake path; the server is the authority either way (FR-7).
- **Black-box evals through the plugin's channel, over unit tests alone.**
  The wiring (host above the router, observers on every navigator,
  lifecycle) is where this breaks; a recognizer unit test cannot see it.

## Out of scope

- The dev-request form itself, its validation and its route (arq103).
- Web motion, permission buttons, desktop.
- Attaching screenshots or logs.
- Any change to the Android toolchain, or to sensors_plus beyond 6.1.x.
- Prompt telemetry beyond the feedback `trigger` tag.

## Assumptions

- arq103's route path stays `/admin/dev-requests/new` and its close keeps
  popping to the pusher (RQ12). A change to either is a revision trigger.
- A deliberate shake reaches 2 g of gravity-removed acceleration on
  typical phones; E-7 confirms or retunes it.
- sensors_plus 6.1.x reads the accelerometer on iOS without a runtime
  prompt; only the Info.plist key is needed. E-7's fresh install confirms.
- The one admin route the host pushes is on the root navigator, as every
  `/admin` route is (`app/lib/core/router/app_router.dart:633-674`).

## Discarded considerations

- **Suppress shake in cook mode.** Cook mode is where a report is most
  useful, and the prompt steals nothing there.
- **Offer admins a choice of request or feedback.** Leo asked for the
  dev-request form; Profile's tile already gives admins feedback.
- **A long-press or two-finger gesture as the accessible path.** The tap
  paths already exist (FR-14); a second gesture is no more accessible.
- **Onboarding card or coach mark.** An unprompted popup is the kind of
  interruption this design avoids; one subtitle where feedback-minded
  users look is enough.
- **Re-reading `/me` before routing.** Adds a network call and a spinner to
  the hot path to improve a value the server re-checks anyway.

## Wrap, don't duplicate

- Reuses: `FeedbackSheet` (`app/lib/features/profile/widgets/feedback_sheet.dart:13`)
  and `FeedbackCacheService`
  (`app/lib/features/profile/services/feedback_cache_service.dart:17`);
  Profile's flush loop, moved, not rewritten
  (`app/lib/features/profile/profile_screen.dart:106-154`);
  `AuthService.isAdmin` (RQ2); `PerfFlagsService` and `GET /v1/flags/perf`
  (RQ5); the router's admin redirect (`app/lib/core/router/app_router.dart:225`);
  arq103's `AdminDevRequestNewScreen.routePath` (RQ12); the branch
  observer lists (RQ6); the SharedPreferences-backed provider pattern of
  `app/lib/providers/theme_mode_provider.dart`.
- Adds: the recognizer and its motion adapter, the host widget, a
  modal-route observer, the feedback launcher, one flags field and its
  setting, one context field, the device switch and the hint.

## Design

### Recognizer

`ShakeRecognizer` (new, `app/lib/core/shake/shake_recognizer.dart`) is
plain Dart: it takes `MotionSample(x, y, z, t)` in m/s² and emits a
recognition. It imports nothing from Flutter or the plugin, so traces
drive it in a unit test.

FR-3 as an algorithm. Let `a` be the sample vector and `|a|` its
magnitude.

1. A sample is **strong** when `|a| ≥ peakThreshold` (19.6 m/s²).
2. Consecutive strong samples form one **peak**; its direction is the unit
   vector of its largest sample. A strong sample whose direction has a
   negative dot product with the open peak's closes it and opens a new
   one.
3. A new peak is a **reversal** of the previous one when their directions'
   dot product is negative and the gap between them is within
   `[minGap, maxGap]` (70–500 ms). Otherwise the run restarts at the new
   peak.
4. `maxGap` with no strong sample ends the run.
5. A run of `minReversals` (4) reversals is a recognition. The recognizer
   then ignores input for `cooldown` (3 s) and starts a new run.

All values live in one `ShakeTuning` constant. E-2's traces are built
from these numbers, so a retune moves the near-miss traces with it.

`MotionSource` (new, `app/lib/core/shake/motion_source.dart`) is the only
file that imports sensors_plus. It subscribes to
`userAccelerometerEventStream(samplingPeriod: SensorInterval.gameInterval)`
(20 ms, about 50 Hz) and maps events to `MotionSample`.

#### Failure handling

| Class | Disposition |
|---|---|
| Stream error, or a missing sensor | cancel; mark motion unavailable for the session; one `ErrorReporter.log('shake.motion_unavailable')` breadcrumb; no UI |
| Sampling slower than asked (Android gives no guarantee) | the recognizer uses event timestamps, not sample counts, so a slower stream recognizes the same shakes, later |
| Timestamps out of order | the sample is dropped |

### Host

`ShakeHost` (new, `app/lib/core/shake/shake_host.dart`) is a stateful
widget that wraps the router's child inside `PalatefulApp`'s
`MaterialApp.router(builder:)` (`app/lib/main.dart:562`), outside
`PerfOverlay`. It sits above every route and below the
`MaterialApp`, so it reaches the root navigator key
(`app/lib/core/router/app_router.dart:76`) and a `scaffoldMessengerKey`
that `PalatefulApp` now passes to `MaterialApp.router`.

**Eligibility (FR-8)** is recomputed whenever an input changes, and the
subscription follows it: listen when eligible, cancel when not. Inputs:
platform (`defaultTargetPlatform` is iOS or Android, `kIsWeb` false,
`kE2EMode` false), `AuthService` signed in and onboarded (it is a
`ChangeNotifier`, RQ2), the ring (`PerfFlagsService`), the device switch,
the session mute, motion availability, and `AppLifecycleState.resumed`
(the host is a `WidgetsBindingObserver`). `defaultTargetPlatform`, not
`dart:io` `Platform`, so a widget test can set it.

**On a recognition**, the host checks suppression (FR-6) and, if clear,
shows the prompt:

- *Text focus*: `FocusManager.instance.primaryFocus` has an
  `EditableTextState` ancestor (RQ7).
- *Modal on top*: `ModalRouteTracker` reports a `PopupRoute` topmost on
  any navigator (below).
- *Own flow open*: the host's own state (`prompting`, `sheetOpen`), plus
  the router location (`appRouter.routerDelegate.currentConfiguration.uri.path`)
  equal to the dev-request path.
- *Not resumed*, *signed out*: already excluded by eligibility; checked
  again because a recognition can be in flight across a change.

**The prompt (FR-5)** is a `SnackBar(behavior: floating, duration: 4 s,
persist: MediaQuery.accessibleNavigationOf(context))` shown through the
messenger key, so it appears on whatever `Scaffold` is current. `persist`
must be explicit: in Flutter 3.41 a snackbar with an action persists by
default and only `persist` gates its timeout (RQ10), so without it the
prompt never fades. Passing accessible navigation keeps it up for screen
reader users, as FR-5 requires, and lets it fade for everyone else. Copy is fixed: `Send feedback?` / `Report` for a user,
`File a dev request?` / `Request` for an admin, chosen by `isAdmin` at
recognition. The host awaits the snackbar's `closed` reason: `action` →
route; `timeout` or `swipe` → count an ignored prompt (two in a row set the
session mute, FR-4); `hide` or `remove` (another snackbar replaced it) →
neither.

**Routing on tap (FR-7).** The host re-reads `isAdmin`. Admin at both
moments, and the router has the dev-request route
(`appRouter.configuration.findMatch(...)` without error; go_router
17.0.0 `RouteMatchList.isError`, RQ12) → `appRouter.push(routePath)` on
the root navigator, awaited; the pop returns the admin to the screen they
shook on (RQ12). Otherwise → `FeedbackLauncher.open(trigger: shake)`. The
route check is the fail-to-user rule applied to a route that a revert of
arq103 could remove.

**State the host never touches.** It never calls `go`, never pops, never
replaces a route, never requests focus. A sheet or form is pushed over the
current route, so that route's `State` (a cook-mode timer in
`app/lib/features/recipes/cook_mode/cook_mode_screen.dart:77-82`, an
import's progress card, a half-filled field) stays mounted.

### Modal-route tracking

`ModalRouteTracker` (new, `app/lib/core/shake/modal_route_tracker.dart`)
is a `NavigatorObserver` that keeps, per navigator, whether its topmost
route is a `PopupRoute` (push, pop, remove, replace). One instance is
added to the root observer list (`app/lib/core/router/app_router.dart:248`)
and to each branch's list (`:731`, `:765`, `:783`, `:820`, `:842`), which
covers the 82 dialog and sheet call sites without editing any (RQ6).

### Feedback launcher

`FeedbackLauncher` (new,
`app/lib/features/profile/services/feedback_launcher.dart`) holds what
Profile's `_openFeedbackSheet` and `_flushFeedbackQueue` hold today
(`app/lib/features/profile/profile_screen.dart:106-189`), moved:

- `open(BuildContext, {required FeedbackTrigger trigger, required String route})`
  shows the same bottom sheet with `currentRoute: route`, `trigger` in the
  context, and a platform of `web` when `kIsWeb`, else `ios` or `android`
  from `defaultTargetPlatform` (on web, `defaultTargetPlatform` reports the
  browser's OS, so it must not be read there). Today Profile sends no
  platform on web (`dart:io` throws, `profile_screen.dart:90-104`). The
  route is the router location's path without its query string.
- `flushQueue()` is Profile's loop. `PalatefulApp` calls it at startup once
  signed in, and on every resume (`app/lib/main.dart:439`); Profile keeps
  its own calls, which become calls to the launcher.

`FeedbackSheet` gains a `trigger` parameter that `_buildContext`
(`app/lib/features/profile/widgets/feedback_sheet.dart:87`) adds to the
context; nothing else in the sheet changes.

### Rollout ring and switch

- **Server.** `Settings.shake_report_ring: Literal["off", "admins",
  "everyone"] = "admins"` beside the latency settings
  (`services/api/src/config.py:66`); an invalid value fails startup.
  `GetPerfFlags.Response` gains `shake_report`
  (`services/api/src/api/v1/flags/get_perf_flags.py:28`). Terraform: a
  `shake_report_ring` variable (default `admins`) mapped to
  `SHAKE_REPORT_RING` in the API container's environment
  (`terraform/modules/ecs/main.tf:277`).
- **Client.** `PerfFlagsService` (`app/lib/core/services/perf_flags_service.dart:74`)
  parses `shake_report`, stores the last valid value under the
  SharedPreferences key `shake_report_ring`, exposes `shakeRing`, and
  notifies listeners when it changes. Before a first valid answer it
  returns the stored value, else `admins`. An unknown string is ignored.
- **Device switch.** A SharedPreferences-backed notifier (key
  `shake_report_enabled`, default `true`) in the pattern of
  `theme_mode_provider.dart`, shown as a `SwitchListTile` in Profile's
  Settings section on iOS and Android.
- **Hint.** Profile's Send Feedback tile subtitle
  (`app/lib/features/profile/profile_screen.dart:857-859`) switches to the
  FR-12 copy for a non-admin while shake is eligible.

### Interfaces

| Surface | Change |
|---|---|
| `GET /v1/flags/perf` | adds `"shake_report": "off" \| "admins" \| "everyone"` |
| `POST /v1/users/me/feedback` | `context.trigger`: `"profile"` \| `"shake"` \| absent; anything else 422 |
| `ShakeRecognizer.add(MotionSample)` → `Stream<void> recognitions` | new |
| `MotionSource.samples` → `Stream<MotionSample>` | new; the plugin seam |
| `FeedbackLauncher.open(context, trigger:, route:)`, `.flushQueue()` | new; Profile and the host call it |
| `PerfFlagsService.shakeRing` | new getter; `ChangeNotifier` |
| Route pushed for admins | `/admin/dev-requests/new` (`AdminDevRequestNewScreen.routePath`, imported, not copied) |

### Data

- `user_feedbacks.context` (JSON) may carry `trigger`. No migration: the
  column is free-form JSON validated at the endpoint.
- SharedPreferences: `shake_report_ring` (string), `shake_report_enabled`
  (bool).
- Terraform: one variable, one container environment entry.

## Migration plan

1. The server accepts `trigger` and serves `shake_report` (default
   `admins`). Deployed before anything below, because the merge is the
   deploy and step 2 sends `trigger`.
2. The launcher replaces Profile's opener and flush, and sends `trigger:
   profile`. Profile behaves as before; queued feedback now sends from any
   screen.
3. sensors_plus 6.1.x and the Info.plist key, with the recognizer, unwired.
   CI's iOS, Android and web builds show the dependency is safe on its own.
4. The host, the tracker and the prompt, routing every admitted user to
   feedback. The ring is `admins`, so only admins see it: dogfood.
5. The device switch and the hint.
6. Admins route to the dev-request form, once arq103's route is on
   `main`.
7. Leo runs E-7, then sets the terraform ring to `everyone`.

Each step is revert-safe except 1's contract: once clients send `trigger`,
removing it from the server makes their feedback 422. Rolling back step 1
after step 2 has shipped means shipping a client without `trigger` first.

## Decision log

| Date | Decision | Record |
| --- | --- | --- |
| 2026-11-25 | Separate workstream from admin-request-intake | [separate-workstream](../decisions/2026-11-25-separate-workstream.md) |

## Unresolved design questions

- Does iOS's Shake to Undo alert appear over a focused Flutter field? FR-6
  keeps the prompt from stacking on it either way; E-7 records the answer.
  Blocks no P0.
- FR-3's numbers on real phones — E-7. Blocks no P0: E-2 pins behavior at
  the current numbers.

## Glossary

- **Ring** — who the server lets shake: `off`, `admins`, `everyone`.
- **Recognition** — the recognizer deciding a run of motion was a shake.
- **Prompt** — the snackbar between a recognition and any form.
