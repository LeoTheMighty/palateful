# Story notif-4: Onboarding notification-permission step

**Status:** in-progress
**Epic:** epic-notifications-ios-proofoflife

## Goal
Insert a single-screen notification-permission step into onboarding, between Welcome (name) and Start Method (browse/import/scratch). Record the OS `AuthorizationStatus` outcome (not which button the user tapped) so the in-app state matches reality. Ship the column + migration so the backend persists it.

## Scope
- New Flutter screen `OnboardingNotificationPermissionScreen` with `Turn on notifications` / `Not now` buttons.
  - `Turn on` invokes `FirebaseMessaging.instance.requestPermission(...)` and records the status based on returned `AuthorizationStatus`:
    - `authorized` → `"granted"`
    - `provisional` → `"provisional"`
    - `denied` / `notDetermined` → `"declined"`
  - `Not now` skips the OS prompt, records `"declined"`.
  - Either choice proceeds to `/onboarding/start` with both `name` and `notification_permission_status` forwarded.
  - On web (where applicable), the step auto-skips by immediately advancing with `"declined"`.
- New route `/onboarding/notifications` wired into `app_router.dart`.
- `OnboardingWelcomeScreen` pushes to `/onboarding/notifications` instead of `/onboarding/start`.
- `OnboardingStartScreen` accepts `notificationPermissionStatus` and forwards it to `completeOnboarding`.
- `ApiClient.completeOnboarding` accepts the optional field.
- Backend `complete_onboarding` endpoint persists `notification_permission_status` on the user (if provided).
- Backend schema `OnboardingRequest` validates the field as `Literal["granted", "provisional", "declined"]` (invalid values rejected with 422).
- User model adds nullable `notification_permission_status: String` column.
- Alembic migration `20260417100000_add_user_notification_permission_status.py` (revision `n1o2t3i4f5p6`, depends on `a1r2e3c4u5r6`).

## File List
- `app/lib/features/onboarding/onboarding_notification_permission_screen.dart` — new
- `app/lib/features/onboarding/onboarding_welcome_screen.dart` — route change
- `app/lib/features/onboarding/onboarding_start_screen.dart` — accept + forward status
- `app/lib/core/router/app_router.dart` — new route + extras wiring
- `app/lib/core/services/api_client.dart` — `completeOnboarding` optional param
- `app/test/onboarding_screen_test.dart` — 6 new tests (4 status mapping + 1 layout + 1 Not-now no-OS-prompt)
- `services/api/src/schemas/user.py` — `OnboardingRequest.notification_permission_status: Literal | None`
- `services/api/src/api/v1/user/complete_onboarding.py` — persist field on user
- `services/api/tests/test_user.py` — 4 new tests (granted / declined / absent / invalid)
- `libraries/utils/utils/models/user.py` — new column
- `services/migrator/migrations/versions/20260417100000_add_user_notification_permission_status.py` — new migration

## Notes

**Migration conflict with uncommitted calendar WIP (local only).** The workspace has an uncommitted `20260417000002_add_calendars.py` that also chains off revision `a1r2e3c4u5r6`. Locally this creates an Alembic branch point, but CI runs against committed code only — my migration is a clean linear descent there. When cal-found-1 is eventually committed, their migration will need `down_revision` rebased to `n1o2t3i4f5p6`.

**Permission-status semantics are codified in both Flutter and Python schema.** The Python `Literal["granted", "provisional", "declined"]` rejects any other value with 422, so a client bug sending `"unknown"` or `"notDetermined"` fails fast instead of silently storing bad state.

**The status reflects OS outcome, not button intent.** `notDetermined` (user tapped "Turn on" then dismissed the system prompt) → `"declined"` — the app state agrees with reality (no permission granted). Key design call from the epic.

## QA walkthrough
See `notif-4-qa-walkthrough.md`.
