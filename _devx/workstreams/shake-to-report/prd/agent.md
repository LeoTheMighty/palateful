# PRD — Shake To Report

<!-- Stage: PRD. Gate: `devx gate prd f89791`. Every concrete item gets a
     stable ID (G-/UC-/CAP-/FR-). IDs are never renumbered. Traceability is
     by ID, not by prose. -->

<!-- Seed: Leo, relayed by the orchestrator tab 2026-11-25: "Shaking as an
     Admin should pull that 'Dev Request' form up, while for a normal user
     it should put up the user feedback UI." A separate workstream from
     admin-request-intake (1e84ad) by decision; see Reference links. -->

## Problem

A Palateful user who hits something broken or missing mid-cook has one way
to say so: leave the screen, open Profile, tap Send Feedback, and describe
from memory a screen they are no longer on. The context that makes a report
useful (where they were) is lost by the time they reach the form, and most
people do not make the trip. Admins are worse off once `admin-request-intake`
ships: the dev-request form sits three taps deep behind the admin dashboard.

A shake gesture opens the right form from any screen, without navigating
away, and records where the user was. Leo's ask: admins get the dev-request
form, everyone else gets the existing feedback sheet.

**Why this is not trivial.** This is a cooking app. Phones are knocked on
counters, carried in pockets, set down hard, and propped up while someone
stirs. A gesture that fires on that motion and takes over the screen while
someone edits a recipe or runs a timer is worse than no gesture. So the
product question is not "detect a shake" but "make a false trigger cost the
user nothing", and that sets the shape of everything below: a two-step
trigger (a prompt the user may ignore, then the form), suppression while
the user is busy, and controls that switch it off without a release.

**What already exists.** No shake detector and no motion-sensor package
(every `shake` in `app/lib` is `tree-shake` or `handshake`;
`app/pubspec.yaml` has no sensor dependency). The feedback sheet
(`app/lib/features/profile/widgets/feedback_sheet.dart`) already captures a
route, queues offline, and is opened only from `profile_screen.dart:156`.
The dev-request form is arq103 of `admin-request-intake`: a route-only
screen at `/admin/dev-requests/new` that returns to whoever pushed it (PR
#132, held for that workstream's bridge; **not on `main`**). The client
learns `is_admin` once per cold start from `/v1/users/me`
(`app/lib/main.dart:219`, `AuthService.isAdmin`).

## Goals

- **G-1** (reach): By 2027-03-31, at least 10 `user_feedbacks` rows carry
  `context.trigger = "shake"`, from at least 3 distinct users.
- **G-2** (false triggers): By 2027-01-31, and before the rollout ring
  moves past admins, the device protocol (E-7) on 1 iOS and 1 Android phone
  records 0 prompts across its 20-minute scripted kitchen session and at
  least 9 of 10 deliberate shakes prompting, on each phone.
- **G-3** (control): From the first production deploy through 2027-03-31,
  a ring change to `off` stops prompts on 100% of online clients within 10
  minutes of the deploy that carries it finishing, with 0 app releases.
- **G-4** (admin path): By 2027-03-31, at least 1 dev request has been
  filed from a phone by shaking, recorded in E-7's Runs table.

## Non-goals

- **Web.** The web build never listens for motion (FR-1). Desktop browsers
  have no accelerometer, and Safari on iOS releases motion data only after
  a permission prompt raised from a tap, which a shake cannot be.
- **Screenshots, annotations or logs attached to the report.** The sheet
  and the form stay as they are; shake adds a route and a trigger tag.
- **Changing the dev-request form.** It belongs to arq103. Shake pre-fills
  nothing and validates nothing, so it inherits that form's rule of never
  refusing text the server would accept.
- **Prompt telemetry** (counts of prompts shown or ignored). Field false
  triggers are measured by the device protocol (G-2), not instrumented.
- **Signed-out visitors.** Feedback needs an account; shake is off on the
  login and onboarding screens.
- **Upgrading the Android toolchain** to take sensors_plus 7.x (FR-2).
- **Any change to iOS's own Shake to Undo.** FR-6 keeps the two from
  stacking; the system alert stays the system's.

## Users

- **Primary — signed-in user on a phone**, usually mid-cook, often with wet
  or busy hands. Wants to report without losing their place.
- **Primary — admin on a phone** (Leo and a handful of known admins). Wants
  to file a dev request about the screen in front of them.
- **Secondary — Leo as operator**: narrows, widens or switches off shake
  for everyone without shipping an app build.
- **Anti-persona**: web users (desktop or mobile browser); signed-out
  visitors; anyone for whom shaking is the only way in — FR-14 keeps a
  tap path for both forms.

## Use cases

- **UC-1**: A signed-in user shakes their phone on any screen, sees a small
  prompt, taps it, and writes feedback that records the screen they were on.
- **UC-2**: A user moves their phone in an everyday way (pocket, walking,
  stirring, a knock or a hard set-down) and nothing appears; if a prompt
  does appear, it fades on its own and leaves the screen as it was.
- **UC-3**: An admin shakes their phone, files a dev request, and is back on
  the screen they were on.
- **UC-4**: A user shakes while typing, while a dialog or sheet is open, or
  while the feedback sheet or the dev-request form is already up, and
  nothing new appears.
- **UC-5**: A user who cannot or will not shake reaches the same forms by
  tapping: Profile → Send Feedback; Profile → Admin Dashboard → Request a
  change.
- **UC-6**: A user turns shake off for themselves in Profile settings.
- **UC-7**: Leo widens shake from admins to everyone, or switches it off,
  without an app release.
- **UC-8**: A user offline shakes, writes feedback, and it is sent when the
  phone is back online, whichever screen they are on then.

## Capabilities

- **CAP-1**: Motion sensing on iOS and Android, only while the app is in
  the foreground and the user is eligible.
- **CAP-2**: Shake recognition that rejects everyday kitchen motion.
- **CAP-3**: A non-modal prompt between recognition and any form.
- **CAP-4**: Suppression while the user is busy or a form is already open.
- **CAP-5**: Role routing that fails to the user path.
- **CAP-6**: One feedback launcher for every entry point, with an app-wide
  offline flush.
- **CAP-7**: Controls: a server-side rollout ring and a per-device switch.
- **CAP-8**: A discoverability hint where feedback-minded users look.

## Feature requirements

### FR-1: Where shake is active

Shake is active only in the iOS and Android app builds. The web build never
subscribes to motion and never shows the FR-12 hint. A build with
`E2E_MODE` set never subscribes, so driver tests see no prompts. Neither
platform shows a permission prompt for it. On a device with no
accelerometer, or when the sensor stream errors, recognition stops for the
rest of the session with one breadcrumb log (not an error report) and no
UI; FR-14's paths are unaffected.

### FR-2: Sensing

The recognizer reads gravity-removed acceleration (sensors_plus
`userAccelerometer`) at about 50 Hz, only while the app is resumed and the
user is eligible (FR-8). It cancels the subscription on pause, sign-out, or
when eligibility ends, and resubscribes when it returns. The dependency is
sensors_plus pinned to the 6.1 line: 7.0 raised its Android floor to AGP
8.12.1, Gradle 8.13 and Kotlin 2.2.0, and the app is on AGP 8.7.3, Gradle
8.12 and Kotlin 2.1.0. From 6.0 the plugin needs `NSMotionUsageDescription`
in `Info.plist`, or the app crashes when it reads motion.

### FR-3: Recognition

A shake is **at least 4 consecutive direction reversals** of acceleration,
where every peak in the run reaches **2.0 g (19.6 m/s²)** in magnitude and
consecutive peaks are **70–500 ms apart**. A peak in the same direction as
the previous one, an interval outside that band, or 500 ms with no peak
resets the run. The values are initial; they change only through E-7 runs,
and they live in one constants block.

Why this shape rejects kitchen motion: in walking or running, the downward
half of each step is bounded by free fall (1 g of gravity-removed
acceleration), so gait cannot produce alternating 2 g peaks; a knock or a
hard set-down is one peak followed by ringing faster than 70 ms; stirring
or kneading with the phone nearby stays well under 2 g.

### FR-4: Cooldown and mute

After a recognition the recognizer ignores motion for 3 s. If two prompts
in a row end without a tap (timed out or swiped away), shake is muted until
the next cold start, so a user whose routine keeps tripping it stops seeing
it without having to find a setting.

### FR-5: The prompt

Recognition shows a floating snackbar on the current screen and nothing
else. A user sees `Send feedback?` with the action `Report`; an admin sees
`File a dev request?` with the action `Request`. It dismisses itself after
4 s and can be swiped away. It takes no focus, does not navigate, and
leaves the screen exactly as it was when ignored. Screen readers announce
it; with accessible navigation on, it stays until dismissed (Flutter's
behavior for a snackbar with an action).

### FR-6: Suppression

A recognition shows nothing, and is not queued for later, while any of
these holds:

- a text input has focus (this also keeps the prompt from stacking on iOS's
  Shake to Undo alert);
- a modal route (dialog, bottom sheet, popup) is topmost on the root
  navigator or on any tab's navigator;
- the prompt is showing, the feedback sheet is open, or the current
  location is the dev-request route;
- the app is not resumed;
- the user is signed out or has not finished onboarding.

The trigger is idempotent with respect to what is already on screen: no
state of the app has two of its forms open because of shakes.

### FR-7: Role routing

On a tap, an admin goes to the dev-request form: the app pushes
`/admin/dev-requests/new` on the root navigator, and closing it returns the
admin to the screen they shook on. Everyone else gets the feedback sheet
(FR-9). An admin is a user for whom `AuthService.isAdmin` was true both
when the prompt appeared and at the tap; any other case takes the user
path. `isAdmin` is the only role source: set from `/v1/users/me` at boot,
false by default, reset on logout. So an unknown role (offline cold start,
`/me` failed, `/me` still in flight) is the user path, never the admin one.

The client's role is routing only. Authorization stays where it is: the
router's `/admin` redirect and the server's `require_admin_async`. A stale
`true` (admin revoked mid-session) opens a form whose submit the server
refuses with 403 and no row, so it cannot start agent work.

### FR-8: Eligibility

Shake listens only when all hold: FR-1's platform rule; signed in and
onboarded; the ring (FR-10) admits this user; the device switch (FR-11) is
on; not muted (FR-4).

### FR-9: One feedback launcher

Every entry point (Profile's Send Feedback tile and shake) opens the
existing feedback sheet through one launcher, which passes the current
route path (without its query string) and a trigger (`profile` or `shake`)
in the sheet's context. The offline queue flushes at cold start and on
every resume, whichever screen is mounted. Today it flushes only while
Profile is mounted (`profile_screen.dart:65`, `:77`), so feedback queued
from a shake elsewhere could wait indefinitely. Profile's tile behaves as
it does today apart from the context it sends.

### FR-10: Server-side ring

`GET /v1/flags/perf` gains `shake_report` ∈ {`off`, `admins`, `everyone`},
read from the API's `SHAKE_REPORT_RING` environment variable, which
terraform sets (default `admins`). The client reads it through the existing
flags fetch (at boot, then every 5 minutes), keeps the last value it
received on the device, and uses `admins` before it has ever received one.
`off` admits no one, `admins` admits only admins, `everyone` admits every
eligible user. Changing the ring is a terraform variable and a deploy; no
app release. A console-made task-definition revision is faster in an
emergency, but the next deploy replaces it, because terraform owns the
task definition's environment (`terraform/modules/ecs/main.tf:277`).

### FR-11: Device switch

Profile → Settings gains a `Shake to report` switch, on by default, stored
on the device and shown only where FR-1's platform rule holds. Turning it
off cancels the subscription at once.

### FR-12: Discoverability

For a non-admin on iOS or Android with shake eligible, the Send Feedback
tile's subtitle reads `Tell us what to build or fix — or shake your phone
on any screen`. No onboarding card, coach mark or unprompted popup. Admins
get no hint: for them shake is an insider shortcut, and the dashboard tile
is their visible path.

### FR-13: The server accepts the trigger

The feedback context (`FeedbackContext`,
`services/api/src/api/v1/user/create_user_feedback.py:69`) gains `trigger`:
`profile`, `shake` or absent. It must be deployed before any client sends
it. The context rejects unknown keys (`extra="forbid"`), and the sheet
queues on any error (`feedback_sheet.dart:126`), so a client that sent
`trigger` first would get 422 on every retry and lose the feedback without
telling anyone.

### FR-14: Paths that need no shake

Feedback: Profile → Send Feedback (exists). Dev request: Profile → Admin
Dashboard → Request a change (arq103's tile). Both stay; shake is an extra
way in, never the only one.

## Evals seed

Promoted to `expectations.md` E-1 … E-10. The P0s are black-box: they boot
the real app in a widget test, feed motion through sensors_plus's platform
channel, and look at what the user would see. Each one also carries a
control that proves it can see.

## Open questions

None blocks Gate 1. Each has a default this PRD already uses.

- Ring at first deploy: `admins`, so Leo and the admins dogfood it; Leo
  moves it to `everyone` after E-7 passes. — owner: user
- Device switch default: on, for everyone the ring admits. — owner: user
- Admins get only `Request` from a shake, not a choice of request or
  feedback; Profile's tile still gives them feedback. — owner: user
- FR-3's numbers are physics-grounded first guesses; E-7 is where they are
  tuned. — owner: research

## Reference links

- Spec: `plan/plan-f89791-2026-11-25T09:02-shake-to-report.md`
- The dev-request form: `admin-request-intake` (1e84ad), phase 3 / arq103,
  PR #132 (`feat/dev-arq103`, head `b9bf7104`),
  `app/lib/features/admin/admin_dev_request_new_screen.dart` on that branch.
- Reused: `app/lib/features/profile/widgets/feedback_sheet.dart`,
  `app/lib/core/services/perf_flags_service.dart`,
  `services/api/src/api/v1/flags/get_perf_flags.py`,
  `AuthService.isAdmin` (`app/lib/core/services/auth_service.dart:180`).
- Why a separate workstream: `decisions/2026-11-25-separate-workstream.md`.
