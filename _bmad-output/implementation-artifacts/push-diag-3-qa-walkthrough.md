# QA Walkthrough — push-diag-3

**Story:** push-diag-3 — Admin per-user push health endpoint + panel + runbook
**Primary verification: Leo on laptop + phone.**

## Backend

- [ ] Start the API locally (or target a staging/prod env with an admin user).
- [ ] As admin, `GET /v1/admin/notifications/health/<your-uuid>` → 200 with full blob.
- [ ] As admin, `GET /v1/admin/notifications/health/<your-email>` → 200, same user resolved.
- [ ] As admin, `GET /v1/admin/notifications/health/<uppercase-EMAIL>` → 200 (case-insensitive).
- [ ] As admin, `GET /v1/admin/notifications/health/<random-uuid-that-doesnt-exist>` → 404.
- [ ] As non-admin → 403.
- [ ] Verify a single `error_logs` row with `service="audit"`, `error_type="AdminPushHealthCheck"` per successful call.
- [ ] `?error_limit=0` or `?error_limit=51` → 422 (FastAPI ge/le validation).

## Admin dashboard

- [ ] Open admin dashboard → scroll to Notifications.
- [ ] New "Check user's push health" panel visible below the test-push panel.
- [ ] Paste your own UUID → Check → panel renders user/email/permission/token-count/error-count/crashlytics-link.
- [ ] Paste your own email → same result.
- [ ] Paste a bogus UUID → "No user found with that UUID or email."
- [ ] After successful lookup, click "Send test push to this user" → push lands on your phone (or returns `no_tokens` if you haven't registered).
- [ ] Click "Crashlytics link" → copies to clipboard, SnackBar confirms.

## Runbook

- [ ] `docs/PUSH_NOTIFICATIONS.md` contains a new section "Diagnosing a user who reports no pushes (push-diag-3)".
- [ ] The runbook walks through the 5-step diagnosis flow + documents the response shape + audit trail.

## Regression checks

- [ ] Existing `POST /v1/admin/notifications/test-push` still works (notif-3 flow).
- [ ] Existing admin tests pass: `pytest tests/test_admin*.py`.

## Expected files touched

- `services/api/src/api/v1/admin/get_push_health.py` (new)
- `services/api/src/api/v1/admin/__init__.py`
- `services/api/src/routers/v1/admin_router.py`
- `services/api/tests/test_admin_push_health.py` (new, 7 tests)
- `app/lib/core/services/api_client.dart`
- `app/lib/features/admin/admin_dashboard_screen.dart`
- `docs/PUSH_NOTIFICATIONS.md`
