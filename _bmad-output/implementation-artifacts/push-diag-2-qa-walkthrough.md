# QA Walkthrough — push-diag-2

**Story:** push-diag-2 — Harden loud-on-boot prompt
**Primary verification is on Leo's iPhone via TestFlight — this is the epic's golden-path success criterion.**

## Golden path — Leo's existing account, `notDetermined`, past-onboarding

- [ ] Install TestFlight build with push-diag-1 + push-diag-2.
- [ ] Open the app.
- [ ] **Within ~2 seconds of the home screen rendering, the OS permission prompt appears.**
- [ ] Tap Allow.
- [ ] Xcode console / Crashlytics logs contain the full breadcrumb sequence:
  - `push.ensureRegistered: entered, platform=ios, autoPrompt=true, attempts=0`
  - `push.ensureRegistered: status=notDetermined`
  - `push.ensureRegistered: calling requestPermission (attempt 1/3)`
  - `push.ensureRegistered: post-prompt status=authorized`
  - `push.ensureRegistered: granted, fetching token`
  - `push.ensureRegistered: completed, final_status=authorized, attempts=1`
- [ ] Open the admin dashboard, send test push to self. Push lands.

## Regression check 1 — Brand-new user path (notif-4 owns the prompt)

- [ ] Delete/reset the app. Create a fresh account.
- [ ] **Boot-time prompt does NOT appear** before onboarding.
- [ ] Onboarding runs to the notif-4 step. Tap "Turn on notifications".
- [ ] OS prompt appears from notif-4's code path, not the boot path.
- [ ] Xcode console shows `push.ensureRegistered: autoPrompt=false, skipping requestPermission` when the app first boots (since `hasCompletedOnboarding=false`).
- [ ] After onboarding completes and the user backgrounds/foregrounds the app, the resume-path `ensureRegistered(autoPrompt: true)` runs — if status is still `notDetermined` (shouldn't be), it would prompt.

## Regression check 2 — `denied` user

- [ ] Existing user who previously denied.
- [ ] Open the app. **No prompt fires.** (iOS does not re-prompt on `denied`; the code respects it and skips.)
- [ ] Navigate to Profile → Notifications. The existing `_buildOsPermissionWarning` card appears with "Open Settings".
- [ ] Xcode console shows `push.ensureRegistered: denied, no-op`.
- [ ] Tap Open Settings → flip iOS notifications on → return to app.
- [ ] Resume-path `ensureRegistered(autoPrompt: true)` sees `authorized` → fetches token → registers with backend.

## Regression check 3 — Retry budget

- [ ] Simulate Firebase misbehaving (e.g., kill the Firebase config key) so `requestPermission` returns `notDetermined` every call.
- [ ] Cold start → prompt attempt #1 (fails to actually prompt).
- [ ] Background/resume → prompt attempt #2.
- [ ] Background/resume → prompt attempt #3.
- [ ] Background/resume → **no further attempts**, breadcrumb "max retry attempts reached this launch".
- [ ] Force-quit and re-open → attempts counter resets (fresh 3 attempts).

## Firebase init race

- [ ] Very hard to reproduce on device — happens only if `Firebase.initializeApp()` hasn't completed before `ensureRegistered` is called.
- [ ] If it happens: Crashlytics shows `area=push, operation=ensureRegistered.firebaseNotReady` with a `StateError`. No crash, no user-visible change.

## Expected files touched

- `app/lib/core/services/push_notification_service.dart`
- `app/lib/main.dart`
- `app/lib/features/profile/notification_preferences_screen.dart`
- `app/test/core/services/push_notification_service_test.dart` (+7 tests)
