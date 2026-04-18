# QA walkthrough — arh-1: POST_NOTIFICATIONS + runtime prompt + FCM channel

## Smoke prerequisites

- Android 13 (API 33) or Android 14 (API 34) emulator is the minimum
  target — on pre-13 the OS silently grants notifications and this story
  is a no-op.
- A registered FCM test payload that specifies
  `android.notification.channel_id=palateful_default`.

## Checklist

- [ ] `adb install` the release APK / AAB onto a fresh Pixel 7 API 34
      emulator.
- [ ] Open the app. Authenticate. On the onboarding "Stay in the loop"
      screen, tap **Turn on notifications**. Confirm:
  - [ ] Native OS dialog titled "Allow Palateful to send you
        notifications?" appears.
  - [ ] Tap **Allow**. No crash; onboarding advances to the next step.
- [ ] Navigate to Settings → Apps → Palateful → Notifications. Confirm:
  - [ ] A channel "Palateful Notifications" is listed.
  - [ ] Importance is High (sound + pop on screen).
  - [ ] Badge is enabled.
- [ ] Send a test push from the backend (admin console → "Send test
      push"). Confirm:
  - [ ] Notification appears in the shade under the "Palateful
        Notifications" channel label.
  - [ ] Tapping it deep-links to the expected route.
- [ ] Repeat from a fresh install but tap **Not now** at the permission
      step. Confirm:
  - [ ] App continues; home screen loads.
  - [ ] Settings → Apps → Palateful → Notifications is OFF; toggling it
        ON re-enables delivery.
  - [ ] Sending a test push while OFF → push is delivered to the device
        but suppressed by the OS (expected).

## Unit test coverage (runs in CI)

- `flutter test test/core/services/push_notification_service_test.dart`
  exercises the Android-only channel-creation branch via
  `_AndroidPushNotificationService` subclass (`isAndroid=true`,
  `isFirebaseReady=true`). Three new assertions:
  1. Channel is created exactly once across repeated `ensureRegistered`
     calls, with id `palateful_default`, name "Palateful Notifications",
     `Importance.high`, and `showBadge=true`.
  2. Non-Android path skips channel creation entirely.
  3. Plugin-side failure surfaces as an
     `operation: 'androidChannel.create'` `ErrorReporter` report
     without crashing the boot path.

## Out of scope

- Android 12 fallback flow (manifest declaration is ignored pre-13; no
  QA needed).
- Custom notification sound selection (v2).
