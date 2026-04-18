# Story notif-1: iOS AppDelegate + Info.plist + APNs registration

**Status:** in-progress
**Epic:** epic-notifications-ios-proofoflife

## Goal
Wire iOS native AppDelegate to forward the APNs device token into Firebase Messaging and add the two Info.plist keys required for iOS to grant a push delivery path. Flutter's `firebase_messaging` plugin drives the actual `registerForRemoteNotifications()` call post-permission-grant; this story's AppDelegate work is the token-pairing bridge plus a belt-and-braces safety net.

## Scope (from epic)
- AppDelegate sets `Messaging.messaging().delegate = self` and `UNUserNotificationCenter.current().delegate = self` in `didFinishLaunchingWithOptions`.
- AppDelegate does NOT call `FirebaseApp.configure()` (the plugin does) and does NOT call `registerForRemoteNotifications()` unconditionally in `didFinishLaunchingWithOptions` (would register without permission).
- `didRegisterForRemoteNotificationsWithDeviceToken` → `Messaging.messaging().apnsToken = deviceToken`. **Load-bearing change.**
- `didFailToRegisterForRemoteNotificationsWithError` → `print` with the error.
- UNUserNotificationCenter safety net: observe authorization transitions; when `.authorized` or `.provisional` AND `isRegisteredForRemoteNotifications == false`, call `registerForRemoteNotifications()` on the main thread. Gated on authorization status to handle the first-launch race.
- `Info.plist`: `UIBackgroundModes` array with `remote-notification`; `NSUserNotificationUsageDescription` with user-facing copy.
- `Runner.entitlements`: already has `aps-environment=production`. No change.
- Flutter `push_notification_service.dart`: add `debugPrint` on FCM token arrival and on permission-grant authorization status.
- APNs `.p8` upload to Firebase Console is a manual ops step covered by docs in notif-2.

## File List
- `app/ios/Runner/AppDelegate.swift` — modified
- `app/ios/Runner/Info.plist` — modified
- `app/lib/core/services/push_notification_service.dart` — modified (debugPrints)

## Notes

**Divergence from epic AC 2 (justified):** the epic directs "set `Messaging.messaging().delegate = self` and `UNUserNotificationCenter.current().delegate = self`". Doing this would override the firebase_messaging Flutter plugin's own delegate registration (the plugin sets itself as both delegates in its iOS registration in order to forward events to Dart via method channels). Taking those delegates over breaks the plugin's ability to deliver `onMessage`, `onMessageOpenedApp`, and token-refresh callbacks to Dart.

The epic's load-bearing ask is the APNs-token bridge to `Messaging.messaging().apnsToken` — that is preserved. (In fact the plugin also forwards the APNs token on its own via its `FlutterPluginAppLifeCycleDelegate`; our explicit forward is a defensive redundancy.) The AC 5 safety net is implemented via `applicationDidBecomeActive` + `getNotificationSettings`-gated `registerForRemoteNotifications()`, which covers the same regression-guard goal without taking over the plugin's delegates.

- AC 3 (APNs token forward): ✅ `didRegisterForRemoteNotificationsWithDeviceToken` sets `Messaging.messaging().apnsToken`.
- AC 4 (APNs fail log): ✅ `didFailToRegisterForRemoteNotificationsWithError` prints.
- AC 5 + AC 6 (safety net with auth-status gate): ✅ `ensureAPNsRegistered()` called from `applicationDidBecomeActive`, gated on `.authorized`/`.provisional` before calling `registerForRemoteNotifications()` on main.
- AC 7 (Info.plist UIBackgroundModes): ✅.
- AC 8 (Info.plist NSUserNotificationUsageDescription): ✅.
- AC 9 (entitlements aps-environment): ✅ pre-existing.
- AC 10 (.p8 upload ops step): docs land in notif-2.
- AC 11 (manual verification checklist): see QA walkthrough file.

## QA walkthrough
See `_bmad-output/implementation-artifacts/notif-1-qa-walkthrough.md` for the on-device checklist.
