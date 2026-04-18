# Story push-diag-3: Admin per-user push health endpoint + panel + runbook

**Status:** done
**Epic:** epic-notifications-push-diagnostics-hardening

## Goal
Give Leo a single admin-dashboard panel that, given a UUID or email, returns the user's OS permission state, push-token count, recent `service="push_notifications"` error rows, and a link-out to Crashlytics filtered by their Auth0 ID — so the next "I'm not getting pushes" report is diagnosed in minutes instead of raw SQL spelunking. Plus: a runbook section in `docs/PUSH_NOTIFICATIONS.md`.

## Scope

- Backend: new `GetAdminPushHealth` endpoint at `GET /v1/admin/notifications/health/{user_id_or_email}` — admin-only, accepts UUID or email, returns the described JSON blob, writes one `service="audit"` row per call.
- Backend: integration tests A–E (UUID, email, 404, 403, audit row shape).
- Flutter admin dashboard: "Check user's push health" panel under the existing notifications section, renders the JSON blob with a "Send test push to this user" CTA that wires to the existing notif-3 endpoint with `target_user_id`.
- Docs: new "Diagnosing a user who reports no pushes" section in `docs/PUSH_NOTIFICATIONS.md`.

## Out of scope

- `last_successful_send_*` — returned as `null` in this story per epic Locked Decision. Future: scan CloudWatch Logs Insights or add a `push_send_log` table.
- Any new DB tables or migrations.
- Crashlytics integration in the backend (URL is client-side-rendered from a constant + auth0_id).

## Acceptance Criteria (from epic)

1. `GET /api/v1/admin/notifications/health/{user_id_or_email}` — admin-only; UUID or email lookup; 404 if no match.
2. Audit row: `service="audit"`, `error_type="AdminPushHealthCheck"`, message includes target + admin_user_id. One row per request.
3. Admin dashboard: lookup input, Check button, formatted blob, "Send test push to this user" CTA after lookup.
4. Runbook section in `docs/PUSH_NOTIFICATIONS.md`.
5. Backend integration tests A-E.
6. Manual verification: Leo on laptop + phone.

## File List

- `services/api/src/api/v1/admin/get_push_health.py` — NEW endpoint
- `services/api/src/api/v1/admin/__init__.py` — MODIFIED (export)
- `services/api/src/routers/v1/admin_router.py` — MODIFIED (route)
- `services/api/tests/test_admin_push_health.py` — NEW (tests A-E)
- `app/lib/features/admin/admin_notifications_screen.dart` (or wherever notif-3 panel lives — confirm during dev) — MODIFIED (health check UI)
- `app/lib/core/services/api_client.dart` — MODIFIED (add `getAdminPushHealth(idOrEmail)` method)
- `docs/PUSH_NOTIFICATIONS.md` — MODIFIED (runbook section)

## Notes

- `push_tokens` is a JSONB list of strings on `users.push_tokens`, not a separate table. The endpoint exposes only a count + per-token prefix + no metadata — the model doesn't carry `last_seen_at` / `device_type` per-token, so the epic's "push_tokens detail array" simplifies to `{count, prefixes}`. Clearly called out in the response so the admin panel text doesn't overpromise.
- `fcm_token_prefix` is first 8 chars; never return the full token.
- `recent_errors.message` is truncated to 500 chars server-side.
- Email lookup is case-insensitive via `func.lower(users.email) == func.lower(<input>)`.
- UUID detection via `uuid.UUID(...)` try/except.
- `crashlytics_query_url` format: `https://console.firebase.google.com/project/palateful-prod/crashlytics/app/ios:com.palateful.app/search?user_id=<auth0_id>`. Auth0 ID pulled from `users.auth0_sub` if present, else fall back to the app UUID so the link still works.

## QA walkthrough
See `push-diag-3-qa-walkthrough.md`.
