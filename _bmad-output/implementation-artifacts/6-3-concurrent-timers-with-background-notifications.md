# Story 6.3: Concurrent Timers with Background Notifications

Status: done

## Story

As a user,
I want to set and manage multiple concurrent timers during cooking that alert me even when the app is backgrounded,
So that I never miss a timing step.

## Acceptance Criteria

1. The timer displays with 48px+ numerals and counts down
2. I can run multiple timers simultaneously
3. Timers continue running (or correctly reconcile elapsed time) when the app is backgrounded
4. Timer completion triggers a high-priority local notification — time-sensitive on iOS (breaks Focus mode), `Importance.max` on Android (heads-up notification)
5. Tapping the notification returns me to cooking mode for the recipe that set the timer
6. I can cancel or restart any active timer

## Tasks / Subtasks

- [x] Task 1: Add dependencies (AC: #3, #4)
  - [x] Add `flutter_local_notifications: ^18.0.0` to `app/pubspec.yaml` dependencies
  - [x] Add `timezone: ^0.9.4` to `app/pubspec.yaml` dependencies
  - [x] Add `flutter_timezone: ^1.0.4` to `app/pubspec.yaml` dependencies
  - [x] Run `flutter pub get` from `app/` directory

- [x] Task 2: Android manifest — exact alarm permission (AC: #4)
  - [x] Add `<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />` to `app/android/app/src/main/AndroidManifest.xml` (required for exact timer notifications on Android 12+)

- [x] Task 3: Create `CookTimerNotificationService` (AC: #3, #4, #5)
  - [x] Create `app/lib/core/services/cook_timer_notification_service.dart`
  - [x] `initialize()`: init `FlutterLocalNotificationsPlugin`, create Android channel `cook_timers` with `Importance.max`, configure iOS `DarwinInitializationSettings` with `requestAlertPermission: false`
  - [x] `scheduleTimerNotification(int id, String label, DateTime expiresAt, String recipeId)`: calls `flnPlugin.zonedSchedule()` with `AndroidScheduleMode.exactAllowWhileIdle`; iOS uses `DarwinNotificationDetails(interruptionLevel: InterruptionLevel.timeSensitive)`; payload = recipeId
  - [x] `cancelTimerNotification(int id)`: calls `flnPlugin.cancel(id)`
  - [x] `handleNotificationTap(String? payload)`: navigate to `/recipes/$payload/cook`
  - [x] Initialize timezone in `initialize()`: `tz.initializeTimeZones()` + `flutter_timezone`
  - [x] Register in `app/lib/core/di/injection.dart` and initialize in `app/lib/main.dart`

- [x] Task 4: Integrate lifecycle observer in `CookModeScreen` for background reconciliation (AC: #3)
  - [x] Add `WidgetsBindingObserver` mixin to `_CookModeScreenState`
  - [x] In `initState()`: `WidgetsBinding.instance.addObserver(this)`
  - [x] In `dispose()`: `WidgetsBinding.instance.removeObserver(this)`
  - [x] Override `didChangeAppLifecycleState(AppLifecycleState state)`: reconciles elapsed time on resume

- [x] Task 5: Wire `CookTimerNotificationService` into timer start/cancel/complete (AC: #4, #5, #6)
  - [x] Add `int _nextNotifId = 0` field to `_CookModeScreenState`
  - [x] Add `int notifId` field to `_ActiveTimer` class
  - [x] `_startTimer`: assigns notifId, calls `scheduleTimerNotification`
  - [x] `_cancelTimer`: cancels OS notification
  - [x] `_onTimerComplete`: cancels OS notification before SnackBar

- [x] Task 6: Timer detail bottom sheet with 48px+ numerals (AC: #1, #6)
  - [x] Timer chip wrapped with `GestureDetector(onTap: _showTimerDetailSheet)`
  - [x] `_TimerDetailSheet` widget: label at 18px, live countdown at 72px, Cancel + Restart buttons (48dp)

- [x] Task 7: Widget tests (AC: #1–#6)
  - [x] Timer chip renders formatted countdown with MM:SS
  - [x] Close icon fires cancel callback
  - [x] Tapping chip fires onTap callback
  - [x] Circular progress reflects elapsed fraction
  - [x] Detail sheet renders label and 72px countdown
  - [x] Cancel Timer button fires cancel callback
  - [x] Restart button fires restart callback
  - [x] `_formatDuration` unit tests (3 edge cases)
  - [x] Created `app/test/cook_mode_timer_test.dart` — 10 tests, all passing

## Dev Notes

### This Is a Brownfield Story — Do NOT Rewrite Existing Code

`CookModeScreen` already has a fully working timer infrastructure:
- `_activeTimers: List<_ActiveTimer>` — list of concurrent timers
- `_startTimer(Duration, String)` — starts a `Timer.periodic`, adds to `_activeTimers`
- `_onTimerComplete(_ActiveTimer)` — fires on completion (currently only shows SnackBar)
- `_buildActiveTimers()` — renders the horizontal chip strip
- `_ActiveTimer` class — holds `label`, `duration`, `remaining`, `startTime`, `timer`

This story **extends** that infrastructure. Do NOT replace `_timerTick`, the chip strip, or the `_ActiveTimer` class.

### Why flutter_local_notifications Instead of FCM

`Timer.periodic` does NOT advance when the app is suspended by the OS (both iOS and Android). FCM requires a server round-trip — wrong tool for local countdown timers. `flutter_local_notifications` schedules a notification in the **OS scheduler** at `expiresAt`. It fires reliably regardless of app state, including backgrounded, suspended, and even after kill on most Android variants.

### Background Timer Reconciliation (Critical)

When the user backgrounds the app mid-timer:
1. `Timer.periodic` freezes — `remaining` is stale
2. The OS-scheduled notification fires at the correct time (independent of the app)
3. When app resumes, `didChangeAppLifecycleState(resumed)` fires

In the `resumed` handler:
```dart
@override
void didChangeAppLifecycleState(AppLifecycleState state) {
  if (state == AppLifecycleState.resumed) {
    final toComplete = <_ActiveTimer>[];
    setState(() {
      for (final t in _activeTimers) {
        final elapsed = DateTime.now().difference(t.startTime);
        final remaining = t.duration - elapsed;
        if (remaining <= Duration.zero) {
          toComplete.add(t);
        } else {
          t.remaining = remaining;
        }
      }
    });
    for (final t in toComplete) {
      _onTimerComplete(t);
    }
  }
}
```

### `CookTimerNotificationService` Key Implementation

Add to `injection.dart`:
```dart
import '../services/cook_timer_notification_service.dart';
// ...
getIt.registerLazySingleton<CookTimerNotificationService>(() => CookTimerNotificationService());
```

Initialize in `main.dart` when authenticated (alongside PushNotificationService):
```dart
final cookTimerNotifService = getIt<CookTimerNotificationService>();
await cookTimerNotifService.initialize();
```

Full notification scheduling:
```dart
Future<void> scheduleTimerNotification(
    int id, String label, DateTime expiresAt, String recipeId) async {
  final tzTime = tz.TZDateTime.from(expiresAt, tz.local);
  await _plugin.zonedSchedule(
    id,
    'Timer done! ⏰',
    label,
    tzTime,
    NotificationDetails(
      android: const AndroidNotificationDetails(
        'cook_timers',
        'Cooking Timers',
        channelDescription: 'Alerts when cooking timers expire',
        importance: Importance.max,
        priority: Priority.max,
        fullScreenIntent: true,
        playSound: true,
      ),
      iOS: const DarwinNotificationDetails(
        interruptionLevel: InterruptionLevel.timeSensitive,
        sound: 'default',
        presentAlert: true,
        presentSound: true,
      ),
    ),
    androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    payload: recipeId,
  );
}
```

### iOS Time-Sensitive vs DND

`InterruptionLevel.timeSensitive` (iOS 15+) **breaks through Focus modes** (Do Not Disturb, Work, Sleep focus) when the user has allowed "time-sensitive" notifications for the app. It does NOT break full DND. Apple's `.critical` level does break DND but requires entitlement from Apple — do not attempt this without an entitlement. For a cooking timer, time-sensitive is appropriate.

### Android SCHEDULE_EXACT_ALARM

In Android 12 (API 31+), apps must declare `SCHEDULE_EXACT_ALARM` and the user may need to grant it from Settings. `AndroidScheduleMode.exactAllowWhileIdle` works within this permission model. If permission is denied, fall back gracefully (no crash — `zonedSchedule` catches the error). Log the failure via `debugPrint`.

### Timer Detail Bottom Sheet — Static Snapshot

The bottom sheet uses `showModalBottomSheet` which doesn't re-render on parent `setState`. Therefore the sheet shows the countdown at time of opening — it's a **static snapshot**. The live countdown continues in the header chip. The bottom sheet's primary purpose is to provide large-text confirmation and cancel/restart actions.

If live countdown in the sheet is desired in future, use a `StatefulWidget` bottom sheet with its own `Timer.periodic` that closes on `dispose`.

### Restart Timer Logic

"Restart" = cancel existing Dart timer + scheduled notification, create a new `_ActiveTimer` with same label + original duration, schedule new notification:
```dart
// In bottom sheet restart button:
timer.timer?.cancel();
getIt<CookTimerNotificationService>().cancelTimerNotification(timer.notifId);
setState(() => _activeTimers.remove(timer));
_startTimer(timer.duration, timer.label); // _startTimer handles everything else
```

### State Management

`setState` only — consistent with `cook_mode_screen.dart` and all existing import/cook screens. Do NOT introduce Riverpod here.

### DO NOT

- Replace the timer chip strip with the bottom sheet — keep both
- Remove `_timerTick` — it drives the chip countdown display
- Add server-side timer tracking — all logic is local
- Use FCM for timer notifications — use `flutter_local_notifications` only
- Auto-complete timers without showing the notification — the notification IS the UX
- Handle multiple timer notifications in a single combined notification — keep them separate (each timer gets its own notification ID)

### References

- [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart] — Timer infrastructure to extend (lines 145–188 for `_startTimer`/`_onTimerComplete`, lines 397–456 for `_buildActiveTimers`, lines 618–632 for `_ActiveTimer` class)
- [Source: app/lib/core/services/push_notification_service.dart] — FCM init pattern + `_handleNotificationTap` switch for notification routing
- [Source: app/lib/core/di/injection.dart] — DI registration pattern
- [Source: app/lib/main.dart:81–83] — PushNotificationService initialization pattern to follow for CookTimerNotificationService
- [Source: app/android/app/src/main/AndroidManifest.xml] — Add SCHEDULE_EXACT_ALARM permission here
- [Source: _bmad-output/implementation-artifacts/6-2-gesture-navigation-for-messy-hands.md] — Previous story: 64dp button sizing, haptic feedback pattern
- [Source: _bmad-output/implementation-artifacts/6-1-cooking-mode-core-experience.md] — AppColors reference: chocolate (#4A3728), warmIvory (#F5ECD7), terracotta, chocolateDark, chocolateLight

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- `_TimerDetailSheet` is a live-countdown `StatefulWidget` (own `Timer.periodic`) rather than the static-snapshot described in dev notes — provides better UX at no extra complexity cost.
- `_restartTimer` helper added to consolidate cancel + re-start logic (cleaner than inline).

### File List

- app/pubspec.yaml
- app/android/app/src/main/AndroidManifest.xml
- app/lib/core/services/cook_timer_notification_service.dart (NEW)
- app/lib/core/di/injection.dart
- app/lib/main.dart
- app/lib/features/recipes/cook_mode/cook_mode_screen.dart
- app/test/cook_mode_timer_test.dart (NEW)
