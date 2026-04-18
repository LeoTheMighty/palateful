# Story notif-3: Admin test-push endpoint + dashboard button

**Status:** in-progress
**Epic:** epic-notifications-ios-proofoflife

## Goal
Give Leo a deterministic "send a real FCM push to my own phone" trigger from the admin dashboard so he can prove — and later diagnose — the round-trip on demand, without having to rely on real event firehose triggers or the staging pipeline.

## Scope
- `POST /api/v1/admin/notifications/test-push` — admin-only, rate-limited (10/min/admin), two-row audit pattern.
  - Request body (all optional): `{title?, body?, target_user_id?}` with defaults `Palateful test push` / `If you see this, pushes work 🍽️` / `current_user.id`.
  - Query: `?force=true` (default). When true, `NotificationType.TEST` bypasses both per-user prefs and quiet hours. When `?force=false` and user is in quiet hours, the send is suppressed and the response carries `suppressed_by_quiet_hours: true`.
  - Rate limit: 10/min/admin_user_id sliding-window. Over-limit: 429 with `{error: "rate_limited", retry_after_s: int}`, no audit row.
  - Audit row (always, on non-rate-limited calls): `error_logs` with `service="audit"`, `error_type="AdminTestPushAudit"`, message `"admin:test_push target=<uuid> by admin_user=<uuid> result=<outcome> message_id=<id>"`. Mirrors `promote_admin.py`.
  - Send-failure row (only on real FCM error): `error_logs` with `service="push_notifications"`, `error_type="PushSendFailure"` — written by `PushNotificationService._log_send_failure` per notif-2, NOT by this endpoint.
  - Response: `{ok, outcome, message_id, target_user_id, log_only, quiet_hours_active, suppressed_by_quiet_hours, success_count, failure_count, tokens_registered}`. `outcome` is the dashboard-friendly enum: `ok | log_only | suppressed_quiet_hours | no_tokens | err`.
- Admin dashboard UI (Flutter, `app/lib/features/admin/admin_dashboard_screen.dart`) — new "Notifications" section with "Send test push" button:
  - Spinner while in flight.
  - Result banner keyed off `outcome` with the right copy for each (`✓ Sent (msg-id: …)`, `log-only mode`, `quiet-hours suppressed`, `no tokens registered`, `error: …`, `Rate-limited. Retry in Ns.`).
  - 429 response parses `retry_after_s` from the failure `data` payload.
- ApiClient method `sendAdminTestPush()` — POSTs to the new endpoint.

## File List
- `services/api/src/api/v1/admin/send_test_push.py` — new
- `services/api/src/api/v1/admin/__init__.py` — export `SendTestPush`
- `services/api/src/routers/v1/admin_router.py` — mount POST route + `force` query param
- `services/api/tests/test_admin_send_test_push.py` — new (7 tests)
- `app/lib/core/services/api_client.dart` — `sendAdminTestPush` method
- `app/lib/features/admin/admin_dashboard_screen.dart` — Notifications section + card

## Notes

**Rate-limit state is module-global.** In-memory, per process. Acceptable for this epic per the workshop decision (tiny admin surface). Worst-case split across multiple API instances gives `N * 10/minute/admin`, which is still well-bounded. Exposed `_reset_rate_limit_for_test()` hook for test isolation.

**AC 7 check-off**: manual verification runs as part of the epic dogfood checklist (see `docs/PUSH_NOTIFICATIONS.md` — Dogfood section). Cannot be asserted by CI.

**Divergence from epic AC 1**: epic's success response called for `{ok, message_id, target_user_id, log_only, quiet_hours_active}`. I layered on `outcome`, `suppressed_by_quiet_hours`, `success_count`, `failure_count`, `tokens_registered` so the dashboard can render the distinct states (log_only, quiet-hours-suppressed, no-tokens, actual success) without re-deriving from a 0-count ambiguity. Strict superset — no breaking change.

## QA walkthrough
See `notif-3-qa-walkthrough.md`.
