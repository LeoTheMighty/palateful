# Story timer-1 — Android notification actions parity

**Status:** ready-for-dev
**Epic:** epic-notifications-timer-actions-live-activities
**Depends on:** none

## Scope

Android notifications for cook-mode timers currently have no inline action
buttons — users must open the app to extend, reset, or stop a timer. iOS
already ships four actions (`TIMER_ADD_2_MIN`, `TIMER_ADD_5_MIN`,
`TIMER_RESET`, `TIMER_DISMISS`) via `DarwinNotificationCategory`. This
story closes the parity gap by wiring `AndroidNotificationAction` entries
onto every scheduled timer notification using the same action IDs, so the
existing `_backgroundNotificationHandler` (platform-agnostic) routes
taps identically on both platforms.

## Decisions / scope cuts

- **Keep the `TIMER_DISMISS` action ID, label it "Stop" on the button.**
  Epic flagged a possible rename to `TIMER_STOP`. Renaming touches iOS
  Swift code (the category registration in `cooking_timer` category uses
  `TIMER_DISMISS`) and the background handler switch. The user-facing
  cost of "dismiss vs stop" is just the button text; keep the ID stable
  and ship the label the user asked for. Flag follow-up if the next epic
  wants true consistency across all new notification surfaces.
- **`cancelNotification: true` on all four actions.** The original
  notification dismisses on any action tap. `TIMER_ADD_2_MIN` /
  `TIMER_ADD_5_MIN` / `TIMER_RESET` schedule a fresh notification;
  `TIMER_DISMISS` just dismisses (no new schedule).
- **`showsUserInterface: false` on all four.** None of these require
  bringing the app to foreground — the background handler schedules a
  new notification entirely from Dart in an isolate.
- **Only the timer notification gets actions.** Meal reminder keeps its
  existing iOS-only actions (Start Cooking / View Recipe / Snooze 15).
  Scope of this epic is timers.

## File list

- `app/lib/core/services/cook_timer_notification_service.dart` [MODIFY]
  — module-level `_timerAndroidActions` list + wire into both the
  background `_scheduleNotification` helper and the instance
  `scheduleTimerNotification` method's `AndroidNotificationDetails`.
- `app/test/cook_timer_notification_service_test.dart` [NEW] — unit
  test asserting the four action IDs and labels are set on Android
  details. Uses a lightweight check against the constructor arg list
  (no real plugin init needed — just verify the shared module-level
  list shape).

## Acceptance criteria

- **AC1** — Module-level constant `_timerAndroidActions` declares
  exactly four `AndroidNotificationAction` entries in order:
  `TIMER_ADD_2_MIN` / "+ 2 min", `TIMER_ADD_5_MIN` / "+ 5 min",
  `TIMER_RESET` / "Reset", `TIMER_DISMISS` / "Stop". All four use
  `showsUserInterface: false`; the constructor default
  `cancelNotification: true` applies.
- **AC2** — Both code paths that schedule a cook-timer notification
  attach this list:
  - Instance method `CookTimerNotificationService.scheduleTimerNotification`
    — passes `actions: _timerAndroidActions` into
    `AndroidNotificationDetails`.
  - Top-level `_scheduleNotification` helper used by the background
    action handler (for the reschedule paths of `TIMER_ADD_2_MIN`,
    `TIMER_ADD_5_MIN`, `TIMER_RESET`) — passes the same list, gated to
    the `cooking_timer` category only (meal_reminder reschedule path
    must NOT get timer actions).
- **AC3** — `scheduleMealReminder` is unchanged; meal notifications do
  NOT get timer actions.
- **AC4** — The existing `_backgroundNotificationHandler` switch-case
  continues to route `TIMER_ADD_2_MIN` / `TIMER_ADD_5_MIN` /
  `TIMER_RESET` / `TIMER_DISMISS` with no modifications — the IDs are
  already platform-agnostic strings. Confirm in dev notes.
- **AC5** — iOS regression: the iOS `DarwinNotificationCategory`
  registration is unchanged. Existing iOS actions must still work.
- **AC6** — Unit test asserts the module-level `_timerAndroidActions`
  list has four entries with the expected `(id, title)` pairs in the
  declared order.

## Manual verification (Android)

Ship-blocking checklist — exercised on an Android emulator + Pixel
device:

- [ ] Schedule a 1-minute timer in cook mode, background the app.
  After 1 min, notification banner shows four action buttons inline
  below the title/body: + 2 min / + 5 min / Reset / Stop.
- [ ] Tap "+ 2 min" → original notification dismisses, a new
  notification fires 2 min later with the same four actions.
- [ ] Tap "Reset" on a fresh 1-min timer → dismisses, new notification
  scheduled at the original 1-min duration.
- [ ] Tap "Stop" → notification dismisses, no reschedule.
- [ ] **Killed-app path:** schedule a 1-min timer, force-quit app via
  task switcher, wait for the notification, tap "+ 2 min". New
  notification scheduled 2 min later. If this path fails on Android
  (platform limitation), document the limitation in the story dev
  notes — the alternative is "user must open the app to extend", but
  iOS already handles killed-app actions correctly via the existing
  handler.
- [ ] iOS regression: same four-action flow on an iPhone still works
  as before (swipe-down on notification to reveal actions).

## Risks / notes

- `flutter_local_notifications` v18.0.1 supports
  `AndroidNotificationAction` since v9+. No plugin bump needed.
- Killed-app delivery of notification actions on Android is a known
  platform quirk depending on OEM battery optimizations. If the Pixel
  test passes, we consider ship-ready; document any OEM-specific
  caveat.
