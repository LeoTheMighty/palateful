# Story push-diag-2: Harden loud-on-boot prompt — retry, race-safe Firebase init, breadcrumbs

**Status:** done
**Epic:** epic-notifications-push-diagnostics-hardening

## Goal
Make the OS permission prompt reliably appear on Leo's next TestFlight launch when his status is `notDetermined`, with resilience against Firebase-init races, `requestPermission` hiccups, and transient failures — *without* pre-empting notif-4's onboarding-owned prompt for brand-new users. Adds a parameterized `ensureRegistered({autoPrompt})`, a 3-attempt in-session retry budget on `notDetermined`, Firebase-readiness assertion, and per-transition breadcrumbs.

## Scope

- New signature: `Future<AuthorizationStatus> ensureRegistered({bool autoPrompt = false})`. Default is `false` so every call site must explicitly opt in to prompting.
- `main.dart` boot + `didChangeAppLifecycleState: resumed` call `ensureRegistered(autoPrompt: authService.hasCompletedOnboarding)`. Pre-onboarding users do NOT get the boot-time prompt — notif-4 owns that flow.
- `notification_preferences_screen.dart`'s `_handlePushToggle` passes `autoPrompt: true` (user-initiated).
- `PushNotificationService` gains `_requestAttempts` counter + 3-strike retry budget scoped to the singleton's lifetime (resets on cold start).
- Firebase readiness asserted via `Firebase.apps.isNotEmpty` before any `FirebaseMessaging` call; if not ready, report `ensureRegistered.firebaseNotReady` and return `notDetermined` without attempting.
- Breadcrumbs at every transition in `ensureRegistered`: entered, status-queried, calling-prompt, post-prompt status, granted-fetching-token, denied-no-op, completed.
- Tests A–G (7 unit tests).

## Out of scope

- User-visible UI changes (none).
- Admin diagnostic endpoint (push-diag-3).
- Changes to notif-4's onboarding prompt (owned by the parent epic, already shipped).

## Acceptance Criteria (from epic)

1. `ensureRegistered({bool autoPrompt = false})` signature; `autoPrompt` default false; call sites updated as described.
2. `Firebase.apps.isNotEmpty` guard; `ensureRegistered.firebaseNotReady` report on miss.
3. Retry policy: 3-strike budget on `_requestAttempts`, only when `autoPrompt: true` AND status is `notDetermined`. Attempt increments AFTER the call. On the 4th+ call, skip `requestPermission`. `autoPrompt: false` with `notDetermined` does NOT call `requestPermission`.
4. Breadcrumbs in the documented order.
5. `main.dart` call updated; `didChangeAppLifecycleState: resumed` updated.
6. Tests A–G pass.
7. `denied`-state handling unchanged.

## File List

- `app/lib/core/services/push_notification_service.dart` — MODIFIED (ensureRegistered signature + retry + Firebase guard + breadcrumbs)
- `app/lib/main.dart` — MODIFIED (pass `autoPrompt: authService.hasCompletedOnboarding` at boot + on resume)
- `app/lib/features/profile/notification_preferences_screen.dart` — MODIFIED (pass `autoPrompt: true` in `_handlePushToggle`)
- `app/test/core/services/push_notification_service_test.dart` — MODIFIED (Tests A–G)

## Notes

- `PushNotificationService` is `registerLazySingleton` in `injection.dart` — confirmed, `_requestAttempts` lifetime matches process lifetime.
- Legacy `initialize()` shim is kept — it's equivalent to `ensureRegistered(autoPrompt: false)`. The only in-tree caller is test code (grep confirms).
- When `authService.hasCompletedOnboarding` is false at boot (pre-`/users/me` response race), `autoPrompt: false` is used and the resume-path re-evaluation catches it.

## QA walkthrough

See `push-diag-2-qa-walkthrough.md`.
