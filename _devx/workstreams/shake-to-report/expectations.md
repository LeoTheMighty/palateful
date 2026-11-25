# Expectations — Shake To Report

<!-- Gate 1 input. Minimum 3 E-blocks (config: engine.expectations_min).
     Every business goal (G-) must be covered by at least one expectation;
     every Covers: ID must resolve in prd/agent.md. EARS regex enforced by
     `devx gate prd`: "When .+, the system SHALL .+". A P0 with a vague
     Verified-by target fails the gate.

     The four P0s are black-box. Each boots the real `PalatefulApp` in a
     widget test, feeds acceleration through sensors_plus's platform
     channel (`dev.fluttercommunity.plus/sensors/user_accel`, payload
     `[x, y, z, timestamp_us]`), answers HTTP with a fake adapter, and
     asserts on what a user would see. Each carries a control that proves
     it can see: a check that passes on unbuilt code is not evidence. -->

## E-1: A deliberate shake opens feedback over the current screen

- **Priority:** P0
- **Covers:** `G-1, UC-1, CAP-1, CAP-2, CAP-3, CAP-6, FR-2, FR-3, FR-5, FR-7, FR-9`
- **Trigger:** The app is signed in as a non-admin with ring `everyone`,
  resting on a screen; a deliberate-shake trace (6 alternating peaks of
  2.5 g, 160 ms apart) arrives on the motion channel; the user taps
  `Report`, types, and sends.
- **Expectation (EARS):** When a signed-in user who is not an admin shakes
  the phone deliberately and taps the prompt, the system SHALL open the
  feedback sheet over the screen they were on and submit, with the
  feedback, that screen's route and the trigger `shake`.
- **Threshold:** exactly 1 prompt with action `Report` within 1 s of the
  trace's last peak; after the tap exactly 1 feedback sheet and an
  unchanged router location beneath it; exactly 1 `POST /v1/users/me/feedback`
  whose `context.route` equals the start route and `context.trigger`
  equals `shake`. Ignored, the prompt is gone after 4 s with 0 sheets and
  the location unchanged. Controls: the fake channel delivers the trace to
  a raw subscriber; the sheet finder finds the sheet when it is opened from
  Profile's tile in the same harness.
- **Measure:** `DATABASE_URL=<prod-url> python services/api/scripts/fetch_feedback.py --since all --status all --format json | python3 -c 'import sys,json; r=[json.loads(l) for l in sys.stdin if l.strip()]; s=[x for x in r if (x.get("context") or {}).get("trigger")=="shake"]; print(len(s), len({x["user_id"] for x in s}))'` · window: first deploy → 2027-03-31 (G-1: ≥ 10 rows from ≥ 3 users)
- **Verified by:** `_devx/workstreams/shake-to-report/evals/E-1_user_path.sh`

## E-2: Everyday kitchen motion never prompts

- **Priority:** P0
- **Covers:** `G-2, UC-2, CAP-2, FR-3, FR-4`
- **Trigger:** In the same harness, eight synthesized traces: walking with
  the phone in a pocket, jogging, stirring with the phone in an apron
  pocket, a knock on the counter, a hard set-down, pounding with a mallet
  on the same counter, and two near-misses (3 reversals at 2.5 g; 6
  reversals at 1.8 g).
- **Expectation (EARS):** When the phone moves the way it does while
  someone carries it, walks, stirs, knocks it or sets it down, the system
  SHALL show no prompt.
- **Threshold:** 0 prompts across all 8 traces (at least 60 s of motion in
  total). Positive control, same session: the E-1 deliberate trace prompts
  exactly once. The eval fails if the control does not prompt, because a
  check that never sees a prompt passes on everyday motion for free.
- **Verified by:** `_devx/workstreams/shake-to-report/evals/E-2_everyday_motion.sh`

## E-3: A shake never interrupts what the user is doing

- **Priority:** P0
- **Covers:** `UC-4, CAP-3, CAP-4, FR-5, FR-6`
- **Trigger:** A deliberate shake arrives while, in turn: a text field
  holds typed text and has focus; a dialog is open on the root navigator; a
  bottom sheet is open on a tab's navigator; the feedback sheet (opened by
  an earlier shake) is open. Then, on a screen running a 1 s periodic timer
  with typed text in an unfocused field, a prompt is ignored, and then
  accepted and the sheet closed.
- **Expectation (EARS):** When a shake arrives while the user is typing, a
  modal is open, or a shake-opened form is already up, the system SHALL
  show nothing and change nothing, and when a prompt is ignored or a sheet
  is closed, the system SHALL leave the screen beneath with its state.
- **Threshold:** 0 prompts and exactly 1 feedback sheet across the four
  busy states; the typed text, the focus and the router location unchanged
  after each. On the timer screen: the same State object survives the
  ignored prompt and the open-close of the sheet, its tick count keeps
  rising throughout, and the typed text is intact. Positive control: the
  same shake on the same screen with nothing busy prompts exactly once.
- **Verified by:** `_devx/workstreams/shake-to-report/evals/E-3_no_interruption.sh`

## E-4: Admins get the dev-request form; anyone uncertain gets the user path

- **Priority:** P0
- **Covers:** `G-3, G-4, UC-3, UC-7, CAP-5, CAP-7, FR-7, FR-8, FR-10`
- **Trigger:** A deliberate shake, then a tap on the prompt, under each of:
  admin with ring `admins`; non-admin with ring `everyone`; admin whose
  `isAdmin` turns false between prompt and tap; admin with ring `off`;
  non-admin with ring `admins`; a non-admin whose flags fetch never
  answers.
- **Expectation (EARS):** When a shake is accepted, the system SHALL open
  the dev-request form only for a user who was an admin both when the
  prompt appeared and at the tap, open the feedback sheet for every other
  admitted user, and show no prompt to a user the ring does not admit.
- **Threshold:** admin: prompt action `Request`, router location
  `/admin/dev-requests/new` with no routing error, 0 feedback sheets, and
  the start location back after the form is popped. Non-admin and
  flipped-admin: action `Report` (non-admin) and a feedback sheet, location
  never `/admin/dev-requests/new`. Ring `off`, ring `admins` for a
  non-admin, and no flags answer: 0 prompts. Controls: the non-admin case
  must prompt, or the 0-prompt cases prove nothing; `/admin/dev-requests/new`
  must be a registered route (arq103, external gate X-1), checked on its
  own so a missing route reads as that, not as a routing bug.
- **Measure:** `E-7` Runs table, kill-switch row · window: first deploy → 2027-03-31 (G-3: 100% of online clients stop prompting within 10 min; G-4: ≥ 1 dev request filed by shaking)
- **Verified by:** `_devx/workstreams/shake-to-report/evals/E-4_role_and_ring.sh`

## E-5: Shake exists only where it can work

- **Priority:** P1
- **Covers:** `FR-1, FR-2`
- **Trigger:** The eligibility rule evaluated for web, iOS, Android and an
  E2E build, and a sensor stream that errors on its first event.
- **Expectation (EARS):** When the app runs on the web, in an E2E build, or
  on a device whose motion sensor is missing or failing, the system SHALL
  not listen for motion and SHALL show no prompt and no hint.
- **Threshold:** web and E2E: 0 subscriptions; iOS and Android: 1; a
  stream error: subscription cancelled, 0 prompts for the rest of the
  session, exactly 1 breadcrumb and 0 error reports. `flutter build web
  --release` succeeds (CI's existing step).
- **Verified by:** `app/test/core/shake/shake_eligibility_test.dart`

## E-6: The server serves the ring and accepts the trigger

- **Priority:** P1
- **Covers:** `UC-7, CAP-7, FR-10, FR-13`
- **Trigger:** `GET /v1/flags/perf` with `SHAKE_REPORT_RING` unset, set to
  each value, and set to an invalid value; `POST /v1/users/me/feedback` with
  `context.trigger` of `shake`, `profile`, absent, and `wiggle`.
- **Expectation (EARS):** When a client asks for its flags or submits
  feedback with a trigger, the system SHALL return the configured ring
  (default `admins`) and SHALL store a valid trigger in the feedback's
  context.
- **Threshold:** the flags response carries `shake_report` equal to the
  configured value, `admins` when unset; an invalid value fails settings
  validation at startup; `shake` and `profile` are stored, absent stores
  none, `wiggle` returns 422 and writes no row. `npx nx run api:test` stays
  at 100% coverage.
- **Verified by:** `services/api/tests/test_shake_flags_and_trigger.py`

## E-7: The device protocol

- **Priority:** P1
- **Covers:** `G-2, G-3, G-4, FR-1, FR-3, FR-4`
- **Trigger:** Leo runs a scripted 20-minute kitchen session with a
  release build on 1 iOS and 1 Android phone (pocket, walking, stirring,
  counter knocks, hard set-downs, phone propped during cook mode), then 10
  deliberate shakes per phone, a fresh install, an admin shake on a phone,
  and a ring change to `off`.
- **Expectation (EARS):** When the app is used through a normal cooking
  session on a real phone, the system SHALL show no prompt, and when the
  user shakes deliberately, the system SHALL prompt.
- **Threshold:** per phone: 0 prompts in the 20-minute session; at least 9
  of 10 deliberate shakes prompt; 0 motion-permission prompts on a fresh
  install; an admin shake files 1 dev request from the phone; after the
  `off` deploy finishes, 0 prompts within 10 minutes.
- **Verified by:** `_devx/workstreams/shake-to-report/evals/E-7_device_protocol.md`

## E-8: Feedback sends from wherever the user is

- **Priority:** P1
- **Covers:** `UC-8, CAP-6, FR-9`
- **Trigger:** Feedback is queued offline from a shake on a screen other
  than Profile; the app then resumes online with Profile never mounted.
  Separately, Profile's Send Feedback tile is tapped.
- **Expectation (EARS):** When the app starts or resumes online with
  feedback queued, the system SHALL send it, whichever screen is mounted.
- **Threshold:** 1 queued item sent in 1 `POST /v1/users/me/feedback`, queue
  length 0 afterwards, and 0 builds of Profile; Profile's tile opens 1
  sheet whose context carries `trigger` `profile` and route `/profile`.
- **Verified by:** `app/test/features/profile/feedback_launcher_test.dart`

## E-9: A user can turn shake off, and can find out it exists

- **Priority:** P2
- **Covers:** `UC-6, CAP-7, CAP-8, FR-11, FR-12`
- **Trigger:** The `Shake to report` switch is toggled; Profile is shown to
  a non-admin and to an admin, with shake eligible and not.
- **Expectation (EARS):** When a user turns the switch off, the system
  SHALL stop listening at once and remember it across restarts, and when a
  non-admin with shake eligible opens Profile, the system SHALL show the
  hint on the Send Feedback tile.
- **Threshold:** off → 0 subscriptions within one frame and after a
  restart; on → 1. Hint present for an eligible non-admin; absent for an
  admin, on web, with the switch off, and with ring `off`.
- **Verified by:** `app/test/features/profile/shake_settings_test.dart`

## E-10: Both forms stay reachable without shaking

- **Priority:** P1
- **Covers:** `UC-5, FR-14`
- **Trigger:** A user with the switch off taps Profile → Send Feedback; an
  admin with the switch off taps Profile → Admin Dashboard → Request a
  change.
- **Expectation (EARS):** When shake is off or impossible, the system SHALL
  still open the feedback sheet and the dev-request form by tapping.
- **Threshold:** each tap path opens its form exactly once, with 0 motion
  subscriptions.
- **Verified by:** `app/test/features/profile/non_shake_paths_test.dart`
