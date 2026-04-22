# Story sched-1 — Shopping deadline reminders: schema + beat task + copy

**Status:** done
**Epic:** epic-notifications-scheduled-reminders
**Depends on:** nfn-1 (per-category prefs), nfn-2 (copy library)

## Scope

Backend-only story. Fire a single morning push per user per shopping
list when that user has unchecked items with `due_at::date == today` in
their local timezone. Per-user-per-list-per-day idempotency via a new
join table `shopping_list_user_reminder_state`. The existing
`DeadlineReminderTask` scaffolding (utc-based, 15-min cadence, log-only)
is replaced by the real implementation.

## File list

- `services/migrator/migrations/versions/20260422010000_add_shopping_list_user_reminder_state.py` [CREATE]
- `libraries/utils/utils/models/shopping_list_user_reminder_state.py` [CREATE]
- `libraries/utils/utils/models/__init__.py` [MODIFY] — export new model
- `libraries/utils/utils/services/notification_copy.py` [MODIFY] — add `shopping_deadline_reminder`
- `libraries/utils/utils/services/shopping_notifications.py` [CREATE] — `notify_shopping_deadline_reminder`
- `libraries/utils/utils/tasks/shopping_list_tasks/deadline_reminder_task.py` [REWRITE] — per-user-per-tz logic + state-row idempotency
- `libraries/utils/utils/services/celery.py` [MODIFY] — beat schedule → every 5 min
- `services/api/tests/test_send_shopping_deadline_reminders.py` [CREATE] — scenarios A-G from AC
- `services/api/tests/test_shopping_notifications.py` [CREATE] — copy + notify_shopping_deadline_reminder

## Acceptance criteria

- AC1 — `shopping_list_user_reminder_state` table exists. Composite PK `(user_id, shopping_list_id)`, `last_deadline_reminder_sent_at` DateTime(timezone=True) nullable, cascades on user/list delete.
- AC2 — `ShoppingListUserReminderState` model matches the table, exported from `utils.models`.
- AC3 — Beat schedule entry `shopping-list-deadline-reminders` runs every 5 min (`crontab(minute='*/5')`).
- AC4 — Task logic:
  - Step 1: `SELECT DISTINCT notification_preferences->>'timezone' FROM users`. For each tz, check if wall-clock in that tz is in `[8:00, 8:05)` window.
  - Step 2: for each in-window tz, load users with that tz. For each user, find shopping lists (owner OR active member) that have unchecked items with `due_at::date == today_in_tz`.
  - Step 3: for each (user, list) pair, upsert `ShoppingListUserReminderState`; if state's last sent date < today_in_tz (or NULL), fire notify + update.
  - Per-(user, list) try/except so one failure doesn't kill the batch.
- AC5 — `notify_shopping_deadline_reminder` constructs the notification via copy library, sends via `send_to_user` (per-category prefs + quiet hours apply).
- AC6 — Tests:
  - Test A: 3 unchecked due-today items + user at 8:02 AM in their tz → 1 push, state row with `last_deadline_reminder_sent_at` set.
  - Test B: same run at 8:07 AM same day → no 2nd push (state-row idempotency).
  - Test C: all items checked → no push.
  - Test D: items due tomorrow → no push today.
  - Test E: user at 9:00 AM in their tz → no push (window passed).
  - Test F: `prefs.categories.shopping = false` → suppressed.
  - Test G (shared lists): Leo in MST + Sarah in EST share a list. Only Sarah fires at 12:00 UTC; only Leo fires at 14:00 UTC; neither state row suppresses the other.

## Notes

- Timezone source: `user.notification_preferences["timezone"]` (JSONB), not a separate column. Users with no timezone set are skipped (explicit opt-in).
- Uses `zoneinfo` (stdlib) for tz conversion.
- 5-min beat cadence → [8:00, 8:05) window matches exactly one beat tick per day per tz.
- Old `DeadlineReminderTask` class is rewritten (not deleted — task name `shopping_list_deadline_reminder` kept for backwards-compat).

## QA walkthrough

See `sched-1-qa-walkthrough.md`.
