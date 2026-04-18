# Story push-diag-1: Flutter + iOS — route every push failure through ErrorReporter

**Status:** done
**Epic:** epic-notifications-push-diagnostics-hardening

## Goal
Replace every silent `debugPrint` in the push-notification pipeline with a Crashlytics-backed `ErrorReporter.report` call tagged `area: 'push'` and a precise `operation:` tag, plus bridge iOS AppDelegate APNs failures (error callback + 10s registration timeout) to Flutter via a `palateful/push` MethodChannel. Net result: every push failure in TestFlight becomes a queryable Crashlytics non-fatal with platform, permission state, and backend status context — no user-visible change.

## Scope

- Rewire the nine `debugPrint`-in-catch sites in `push_notification_service.dart` to `ErrorReporter.report(..., area: 'push', operation: <tag>, extras: {...})`.
- Add a new error path for the "permission granted but getToken returned null" case (today a `debugPrint`).
- New MethodChannel `palateful/push` — iOS-side `apnsRegistrationFailed` + `apnsRegistrationTimeout` invocations; Flutter-side handlers wired in `ensureRegistered` and report via `ErrorReporter`.
- Supplement the save-preference-failure SnackBar in `notification_preferences_screen.dart` with an `ErrorReporter.report` call (do not remove SnackBar — user-initiated action warrants user feedback).
- Introduce minimal test infrastructure: `@visibleForTesting` hooks on `ErrorReporter` so tests can observe `report`/`log` calls; lightweight `PushMessagingClient` wrapper so `PushNotificationService` is testable without Firebase bootstrap.
- Flutter unit tests for the three listed operations (outer catch, null-token-after-grant, backend register failure).

## Out of scope

- No retry policy / bounded-attempts logic — that is push-diag-2.
- No admin-side health endpoint — that is push-diag-3.
- No user-visible UI changes.

## Acceptance Criteria (from epic)

1. Every `catch` block in `push_notification_service.dart` that currently `debugPrint`s is replaced with `ErrorReporter.report(e, st, area: 'push', operation: <tag>, extras: {...})`. Tags match the epic table.
2. `getToken()` returning null after granted permission reports as `operation: 'getToken.nullAfterGranted'` with a `StateError`.
3. Every `report` call includes `platform` and `auth_status` in `extras` at minimum; `fcm_token_prefix` / `backend_status_code` where meaningful.
4. `AppDelegate.swift` `didFailToRegisterForRemoteNotifications` posts `apnsRegistrationFailed` on channel `palateful/push`. 10s timer post-`registerForRemoteNotifications()` posts `apnsRegistrationTimeout` if success callback hasn't fired.
5. Flutter-side MethodChannel listener wired in `ensureRegistered` (idempotent via `_listenersAttached`), reports each invocation via `ErrorReporter`.
6. `notification_preferences_screen.dart` save-catch keeps SnackBar + adds `ErrorReporter.report(..., operation: 'preferences.save')`.
7. Flutter unit tests A/B/C.
8. iOS: no unit tests; manual verification via TestFlight / Crashlytics dashboard.
9. Manual verification checklist: TestFlight install → breadcrumbs visible → forced backend 5xx → `registerToken.backend` appears.
10. No user-visible behaviour change.

## File List

- `app/lib/core/services/error_reporter.dart` — MODIFIED (add `@visibleForTesting` hooks on `report` + `log`)
- `app/lib/core/services/push_notification_service.dart` — MODIFIED (rewire all `debugPrint`-in-catch → `ErrorReporter.report`, add MethodChannel listener, lightweight `PushMessagingClient` wrapper for testability)
- `app/lib/features/profile/notification_preferences_screen.dart` — MODIFIED (supplement save-catch with `ErrorReporter.report`)
- `app/ios/Runner/AppDelegate.swift` — MODIFIED (MethodChannel invocations on fail + 10s timeout)
- `app/test/core/services/push_notification_service_test.dart` — NEW (tests A/B/C)
- `app/test/core/services/error_reporter_test.dart` — NEW (exercise the test hooks)

## Notes

- `MethodChannel('palateful/push')` — grepped `app/ios` + `app/lib`; no existing channel by that name.
- Full FCM tokens are never logged. `fcm_token_prefix` is first 8 chars. Matches the existing `push_notification_service.dart:136` style.
- `ErrorReporter.report` fallback to `debugPrint` in debug/E2E/web (see `error_reporter.dart:49-50`) preserves existing local-dev behavior. No nested catches — if `report` itself throws, Crashlytics already has a root fatal handler.
- Backend `DioException` status code extraction: `error is DioException ? error.response?.statusCode : null`.

## QA walkthrough

See `push-diag-1-qa-walkthrough.md` for the on-device checklist.
