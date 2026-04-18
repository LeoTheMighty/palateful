# QA Walkthrough — push-diag-1

**Story:** push-diag-1 — Flutter + iOS ErrorReporter integration
**Manual verification primarily on Leo's iPhone via TestFlight.**

## Pre-reqs

- TestFlight build containing push-diag-1 installed.
- Crashlytics dashboard access for the Palateful Firebase project.
- Admin dashboard access (for Section C).

## A — Happy path: sign in, confirm breadcrumbs arrive

- [ ] Fresh cold start. Sign in as a test user whose permission is `authorized`.
- [ ] Wait ~5–10s.
- [ ] Open Crashlytics → Logs. Look for an ensureRegistered run (no events since it's a happy path).
- [ ] No Crashlytics non-fatal is expected — this is the baseline.

## B — Force a backend 5xx and confirm `registerToken.backend`

- [ ] Temporarily break `/v1/users/me/push-tokens` in a dev branch (e.g., raise a 503).
- [ ] Deploy backend to a staging environment OR run locally and point the app at it.
- [ ] Sign in again on a TestFlight build pointed at the misbehaving backend.
- [ ] Crashlytics → Non-fatals:
  - Event with `area=push`, `operation=registerToken.backend`.
  - Custom keys: `platform=ios`, `auth_status=authorized`, `fcm_token_prefix=<8 chars>`, `backend_status_code=503`.
  - `http.method=POST`, `http.path=/v1/users/me/push-tokens`.

## C — Force getToken null and confirm `getToken.nullAfterGranted`

- [ ] Hard to reproduce on device directly — this path is only hit when FCM returns a null token despite permission being granted. Unit test B covers the code path. Manual verification: confirm via a deliberately broken Firebase config (e.g., revoked API key in the Firebase project) that the resulting error is reported with a meaningful operation tag (will likely be `getToken.exception`, not `getToken.nullAfterGranted`).

## D — APNs failure via MethodChannel (iOS native path)

- [ ] Simulator or device: toggle airplane mode BEFORE launching the app.
- [ ] Install + launch the TestFlight build.
- [ ] Grant permission when prompted (iOS still shows the prompt even offline).
- [ ] Observe Xcode console: `APNs register failed: <domain>#<code>: <desc>`.
- [ ] Crashlytics → Non-fatals (after reconnecting and backgrounding/foregrounding):
  - Event with `area=push`, `operation=apns.registrationFailed`.
  - Custom keys: `ios_error_domain=<e.g. NSCocoaErrorDomain>`, `ios_error_code=<int>`.

## E — 10s registration timeout

- [ ] Rare path — requires APNs to swallow both success and failure callbacks (e.g., a networking stack issue beyond airplane-mode).
- [ ] If reproducible in dev: expect `area=push, operation=apns.registrationTimeout` with a `TimeoutException`.

## F — Profile preferences save failure

- [ ] Sign in. Navigate to Profile → Notifications.
- [ ] With the backend broken (Section B setup), tap any toggle (e.g. Partner Activity).
- [ ] Expected: "Failed to save preference" SnackBar (unchanged user-visible behavior).
- [ ] Crashlytics → Non-fatals: `area=push, operation=preferences.save` recorded.

## Regression checks

- [ ] Re-run the Partner Activity toggle flow in normal (not-broken) backend — no Crashlytics noise.
- [ ] Confirm no new user-visible UI (no banners, no modals, no toasts except the pre-existing preferences-save SnackBar).

## Expected files touched

- `app/lib/core/services/error_reporter.dart`
- `app/lib/core/services/push_notification_service.dart`
- `app/lib/features/profile/notification_preferences_screen.dart`
- `app/ios/Runner/AppDelegate.swift`
- `app/test/core/services/push_notification_service_test.dart`
