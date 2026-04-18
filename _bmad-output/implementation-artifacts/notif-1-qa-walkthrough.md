# notif-1 QA walkthrough (on-device, iOS)

APNs registration cannot be asserted via automated tests — it requires a real iPhone talking to Apple's push service. Run this checklist after a TestFlight build lands on device.

**Pre-req:** APNs `.p8` key has been uploaded to Firebase Console (notif-2 docs cover the procedure).

1. Install latest TestFlight build on iPhone.
2. Launch. Sign in with Auth0.
3. Grant notification permission at the OS prompt (via the notif-4 onboarding step once it ships; until then, via iOS Settings → Palateful → Notifications).
4. In Xcode console (or `Console.app` with device filter = Palateful), confirm in order:
   - [ ] `Push permission outcome: AuthorizationStatus.authorized`
   - [ ] `APNs device token received: <hex-prefix>…`
   - [ ] `FCM token: <token-prefix>…`
   - [ ] `Push token registered with backend`
5. In backend logs, confirm `POST /api/v1/user/push-tokens` landed around the same time with a 200.
6. Kill the app, re-open. In the console, the safety net fires via `applicationDidBecomeActive`. No duplicate registration call (iOS debounces) — this is fine. Confirm no error logs from `ensureAPNsRegistered`.
7. Revoke permission in iOS Settings → Palateful → Notifications → Off. Re-open the app. `applicationDidBecomeActive` fires; the safety-net `getNotificationSettings` returns `.denied`; registration is correctly NOT re-triggered.

If step 4 shows `APNs register failed` instead: check entitlement (`aps-environment`) matches the build target (dev vs prod), and that the app is on a real device (simulator doesn't get APNs tokens pre-iOS 16).

Android side: no changes this story. If Android behavior regresses, file a follow-up.
