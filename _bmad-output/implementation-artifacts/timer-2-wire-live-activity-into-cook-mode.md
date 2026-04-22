# Story timer-2 — Wire LiveActivityService into cook_mode_screen lifecycle

**Status:** ready-for-dev
**Epic:** epic-notifications-timer-actions-live-activities
**Depends on:** none

## Scope

`CookingTimerLiveActivity.swift` (lock-screen banner + Dynamic Island
countdown) exists and is compiled into `PalatefulWidgets`, but Flutter
never calls it. `LiveActivityService` already has the Dart-side method
shape (start / update / complete / end) — this story wires those calls
into the cook-mode timer lifecycle, registers the service with the DI
container, initializes it at boot, and cancels in-flight activities
when the cook-mode screen closes.

## Decisions / scope cuts

- **Swift side is unchanged.** The Swift widget uses
  `Text(endTime, style: .timer)`, which is a native auto-countdown —
  no tick loop needed on the iOS side. Flutter only has to set and
  update the `endTime`; the Dynamic Island re-renders automatically.
- **Minute-cadence updater is kept** per the epic AC2, even though the
  native `.timer` style already handles display freshness. Rationale:
  it re-anchors `endTime = now + remaining` every minute, which
  guarantees the native display stays in sync in the edge case of
  system-clock adjustment or stale Activity state. Cost is ~4 KiB of
  transport per tick — trivial. If future profiling shows battery or
  network cost we can drop to update-on-change only.
- **Step number not passed to the Live Activity.** The existing Swift
  `CookingTimerAttributes` struct doesn't have a step-number field;
  adding one would require a Swift rebuild + App Store binary. The
  `timerLabel` (e.g., "Bake — step 3") already carries the step info
  in human-readable form, so the extra field buys nothing.
- **iOS-only, no-op on Android.** `LiveActivityService` is guarded by
  `Platform.isIOS` already; the wiring calls simply no-op off-platform.
- **Restart path calls end + start.** `_restartTimer` currently does
  `_cancelTimer(t)` then `_startTimer(t.duration, t.label)`. Each of
  those already tripwires the live-activity end + start. No explicit
  "update" path needed for restart.

## File list

- `app/lib/core/di/injection.dart` [MODIFY] — register
  `LiveActivityService` as a lazy singleton.
- `app/lib/main.dart` [MODIFY] — initialize `LiveActivityService`
  alongside `CookTimerNotificationService` at boot (outside E2E mode).
- `app/lib/core/services/live_activity_service.dart` [MODIFY] — no API
  shape change; add dartdoc clarifying the Swift side handles
  rendering and `endTime` is the only mutable field for updates.
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` [MODIFY]
  — inject `LiveActivityService`, call `startTimerActivity` from
  `_startTimer`, `updateTimerActivity` from a minute-cadence periodic
  updater, `completeTimerActivity` from `_onTimerComplete`,
  `endTimerActivity` from `_cancelTimer`, and end every in-flight
  activity in `dispose`.
- `app/test/features/recipes/cook_mode/cook_mode_live_activity_test.dart`
  [NEW] — unit test that the service's public API (start / update /
  complete / end) is callable from Dart with a mocked `LiveActivities`
  plugin; validates the activity id map is cleared after `endAll`.

## Acceptance criteria

- **AC1** — `LiveActivityService` is registered in `injection.dart` as
  a lazy singleton and initialized in `main.dart`. Initialization
  no-ops off iOS (existing guard).
- **AC2** — `_startTimer` in `cook_mode_screen.dart` calls
  `liveActivityService.startTimerActivity(notifId: …, timerLabel: …,
  recipeName: …, duration: …)` immediately after scheduling the OS
  notification. `recipeName` is pulled from the cached recipe payload
  (`_recipe?['name']`) with fallback to `'Recipe'`.
- **AC3** — A single `Timer.periodic(Duration(minutes: 1))` runs while
  `_activeTimers.isNotEmpty` (not per-timer). Each tick iterates the
  active timers and calls `updateTimerActivity(notifId, remaining)`
  for each. The updater is created lazily in `_startTimer` when the
  first timer is added, and torn down in `_cancelTimer` /
  `_onTimerComplete` when `_activeTimers` becomes empty.
- **AC4** — `_onTimerComplete` calls
  `liveActivityService.completeTimerActivity(notifId)` before removing
  the timer from `_activeTimers`. The Swift side shows the "Done!"
  state and auto-dismisses after 5 minutes (existing behavior).
- **AC5** — `_cancelTimer` calls
  `liveActivityService.endTimerActivity(notifId)` (immediate dismiss,
  no "Done!" state).
- **AC6** — `dispose` on the cook-mode screen:
  - Cancels the minute-cadence updater.
  - Calls `liveActivityService.endTimerActivity(notifId)` for each
    remaining `_activeTimer` so activities don't linger after the
    user leaves cook mode.
- **AC7** — All calls into `LiveActivityService` work on Android
  (no-op) and in the E2E test harness. Tests assert no exceptions
  escape.
- **AC8** — Minute-cadence updater respects the user leaving / coming
  back to cook mode: a single screen's updater is bound to the
  screen's `dispose` and has no global state.

## Manual verification (iPhone, TestFlight build)

- [ ] Open cook mode for any recipe with timer steps (e.g. quiche).
- [ ] Start a 30-min timer from a step chip.
- [ ] Lock the phone. Live Activity banner appears on the lock
  screen with the timer label + native countdown.
- [ ] Long-press the notch (Dynamic Island) → expanded view shows
  timer label + countdown + progress bar.
- [ ] After ~1 minute, countdown is still accurate (no divergence
  from Dart-side `remaining`).
- [ ] Start a second 5-min timer. Dynamic Island switches to
  whichever the OS prioritizes (next-to-expire).
- [ ] Tap the cook-mode in-app chip to cancel one of the timers →
  its Live Activity vanishes immediately. The other remains.
- [ ] Wait for a timer to hit 0 → Live Activity transitions to
  "Done!" state (green checkmark); after 5 minutes, the activity
  auto-dismisses.
- [ ] Close cook mode (back button) while a timer is running → the
  Live Activity ends (no orphan lock-screen banner).

## Risks / notes

- **`live_activities` v2.0.0 plugin behavior with multiple concurrent
  activities.** Apple allows multiple simultaneously; UI shows one at a
  time (Dynamic Island compact view) with the OS picking. If the plugin
  caps at one, we log the failure via `ErrorReporter` and the cook-mode
  UI continues working (the Dart-side timer is the authority).
- **Wall-clock drift.** Minute-cadence re-anchoring is a safety net; the
  real tick is Dart-side via `Timer.periodic(Duration(seconds: 1))` in
  `_startTimer`.
- **Cold-kill of app.** If the user force-quits the app, the OS
  notification still fires (already the case pre-epic) but the Live
  Activity stays "frozen" at its last `endTime`. Swift's `.timer` style
  continues counting regardless. Documented but out of scope for this
  epic — persistence of in-memory timer state to survive kills is a
  follow-up.
