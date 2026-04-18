# Story notif-2: Backend log-only mode + send-failure logging + docs

**Status:** in-progress
**Epic:** epic-notifications-ios-proofoflife

## Goal
Make `PushNotificationService` explicit about what happens on every send: deliver via FCM when creds are configured, log-only mode when they aren't (local dev default), and persist a row to `error_logs` with `service="push_notifications"` on every send failure. Add the `force` flag + `NotificationType.TEST` that notif-3's admin endpoint depends on. Ship the full ops runbook at `docs/PUSH_NOTIFICATIONS.md`.

## Scope (from epic)

- **Log-only mode** (init): when neither `FIREBASE_CREDENTIALS_JSON` nor `FIREBASE_CREDENTIALS_PATH` is set, `__init__` logs a single INFO line and all `send_*` calls short-circuit without touching the FCM SDK.
- **Malformed creds** fall back to log-only with an ERROR log, never raise.
- **Per-send logging**: INFO on success (type, target, message_id), ERROR on failure (type, target, FCM exception class, response body). Quiet-hours + pref-disabled + no-tokens also INFO-logged.
- **`force: bool = False`** on `send_to_user` / `send_to_users`: bypasses both user `push_enabled` pref AND quiet hours.
- **`NotificationType.TEST`**: always bypasses per-user prefs (diagnostic). Quiet hours controlled by `force`.
- **Send failures** write `error_logs` row with `service="push_notifications"`, `error_type="PushSendFailure"`. Uses its own DB session so the caller's transaction is untouched.
- **`.env.example`** documents both env vars + log-only default.
- **`docker-compose.yml`** forwards both env vars into `api` + `worker` (shell env passthrough with `${VAR:-}`).
- **`docs/PUSH_NOTIFICATIONS.md`** — full runbook with architecture, APNs `.p8` upload + rotation, iOS requirements, local dev, prod creds, troubleshooting checklist, dogfood checklist, and `Last verified` header with Key ID.
- **Tests A–E per epic AC 9**: init log-only mode, send-in-log-only-mode, FCM-exception → error_logs + no raise, force=True bypasses quiet hours, force=False during quiet hours is suppressed. Plus two bonuses: `NotificationType.TEST` bypasses prefs, no-tokens handled cleanly.

## Return-shape contract

All `send_to_*` methods return dicts that preserve the historical keys (`success_count`, `failure_count`, `cleaned_tokens` on `send_to_user`) and layer in new observability fields:
- `log_only: bool` — whether the call was short-circuited
- `message_id: str | None` — FCM id on success, `"log-only"` in log-only mode, `None` on failure/suppression
- `quiet_hours_active: bool` — whether the target's current clock is inside their quiet-hours window (regardless of whether we suppressed)
- `suppressed_by_prefs: bool` / `suppressed_by_quiet_hours: bool` — strict suppression reasons

Existing callsites (recipe-book / meal-event / shopping-list / friends / invitations) keep working unchanged — they only read the historical keys.

## File List
- `libraries/utils/utils/services/push_notification.py` — refactored (log-only mode, per-send logging, force flag, TEST type, error_logs writes)
- `libraries/utils/test/test_push_notification.py` — new (7 tests)
- `.env.example` — documented FIREBASE_CREDENTIALS_{JSON,PATH}
- `docker-compose.yml` — explicit env passthrough on `api` + `worker`
- `docs/PUSH_NOTIFICATIONS.md` — new runbook

## QA walkthrough
See `notif-2-qa-walkthrough.md`.
