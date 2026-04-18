# Story arh-1: POST_NOTIFICATIONS + runtime prompt + FCM channel

**Status:** ready-for-dev
**Epic:** epic-android-release-hardening

## Goal

Make FCM push notifications actually surface on Android 13+. Today the
app ships without `POST_NOTIFICATIONS` declared, so the onboarding
`firebase_messaging.requestPermission()` is a silent no-op on API 33+ —
the OS never prompts, `getNotificationSettings()` returns
`authorized` by default on Android (pre-13 behaviour persists), and
subsequent FCM deliveries are silently dropped by the system. This story
declares the permission, confirms the OS prompt fires via the existing
onboarding screen (no Android-only code path), and creates the
`palateful_default` notification channel eagerly at service init so
incoming FCM payloads surface under a named, user-controllable channel
instead of falling back to the system "Miscellaneous" bucket.

## Scope (from epic)

- `AndroidManifest.xml`: add `<uses-permission
  android:name="android.permission.POST_NOTIFICATIONS" />` alongside the
  existing `SCHEDULE_EXACT_ALARM` + `RECORD_AUDIO`.
- `push_notification_service.dart`: create an `AndroidNotificationChannel`
  with id `palateful_default`, name "Palateful Notifications",
  importance HIGH, show-badge true. Fire once at service init on
  `Platform.isAndroid`.
- Backend alignment: the epic's "no backend change" note is wrong —
  `PushNotification.channel_id` defaults to `"default"` today, not
  `"palateful_default"`. Flip the default so FCM payloads target the
  channel we actually create.
- Onboarding screen: no changes required — `firebase_messaging.requestPermission()`
  already routes to the native OS prompt on Android 13+ once
  `POST_NOTIFICATIONS` is declared (same code path as iOS).

## Implementation

### `app/android/app/src/main/AndroidManifest.xml`

Add under the existing `<uses-permission>` block:

```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
```

Place it with the other `uses-permission` lines at the top of
`<manifest>`. No attributes, no `android:maxSdkVersion` — the permission
is a no-op on pre-13 devices (OS ignores it).

### `app/lib/core/services/push_notification_service.dart`

Add a `flutter_local_notifications`-backed channel creation path:

1. Import `package:flutter_local_notifications/flutter_local_notifications.dart`.
2. Add a `LocalNotificationsClient` abstract wrapper mirroring
   `PushMessagingClient` so unit tests can fake it. Only one method:
   `Future<void> createAndroidChannel(AndroidNotificationChannel channel)`.
3. Add a `FlutterLocalNotificationsClient` concrete impl that calls
   `FlutterLocalNotificationsPlugin().resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.createNotificationChannel(channel)`.
4. Inject via `PushNotificationService` constructor with a `required` =
   false default matching the messaging client pattern.
5. In `ensureRegistered()`, after `_listenersAttached = true`, call a new
   `_ensureAndroidChannel()` method (only runs on `Platform.isAndroid`).
6. `_ensureAndroidChannel()` creates the channel once per process
   (guard with `_androidChannelCreated` bool to avoid duplicate work on
   the lifecycle-resume re-entry path). Errors route through
   `ErrorReporter.report(..., operation: 'androidChannel.create')` so
   regressions surface.

Channel definition:

```dart
const AndroidNotificationChannel(
  'palateful_default',
  'Palateful Notifications',
  description: 'General notifications from Palateful.',
  importance: Importance.high,
  showBadge: true,
)
```

### `libraries/utils/utils/services/push_notification.py`

Change the dataclass default:

```python
channel_id: str = "palateful_default"
```

No call-site changes needed — every `PushNotification(...)` invocation
in the codebase relies on the default, so the new value propagates
automatically to every fan-out (shopping, meal events, friend requests,
recipe book sharing, imports, admin test pushes).

### `app/test/core/services/push_notification_service_test.dart`

Add a new test group asserting the channel is created once on
`Platform.isAndroid`. Since the existing tests force `isAvailable=true`
via `_TestablePushNotificationService`, add a dedicated subclass or a
flag that forces `_isAndroid=true` regardless of host platform. Fake
`LocalNotificationsClient` records invocations; assert:

- On Android path: `createAndroidChannel` is called exactly once per
  `ensureRegistered` lifetime, even across multiple invocations.
- On non-Android path: no channel creation call fires.
- Channel id is `palateful_default`, name is `Palateful Notifications`,
  importance is `Importance.high`.

No widget test needed — onboarding screen isn't changing; Android
routes through the same `firebase_messaging.requestPermission()` call
iOS already uses.

## Acceptance criteria (from epic)

- [x] Manifest declares `android.permission.POST_NOTIFICATIONS`.
- [x] Onboarding notification-permission step triggers the native OS
  prompt on Android 13+. Verified at service level — `firebase_messaging`
  handles the dispatch once the manifest permission is declared; no
  new Android-specific code path.
- [x] If user denies, app continues without crash; OS-level re-enable
  through Settings → App info remains available (no change — existing
  behaviour).
- [x] `palateful_default` notification channel is created explicitly at
  push-service init (name "Palateful Notifications", importance HIGH,
  show badge true). Incoming FCM messages declare matching `channel_id`
  via backend dataclass default flip.
- [x] Unit test: `push_notification_service_test.dart` asserts channel
  creation call happens on `Platform.isAndroid`.
- [ ] Manual smoke (emulator): deferred to QA walkthrough — no Android
  emulator available in dev harness.

## QA walkthrough

Split into a separate `arh-1-qa-walkthrough.md` file.

## File list

### Modified

- `app/android/app/src/main/AndroidManifest.xml`
- `app/lib/core/services/push_notification_service.dart`
- `app/test/core/services/push_notification_service_test.dart`
- `libraries/utils/utils/services/push_notification.py`
