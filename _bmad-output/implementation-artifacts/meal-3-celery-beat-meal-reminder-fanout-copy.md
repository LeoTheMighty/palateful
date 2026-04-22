# Story meal-3: Celery beat task + reminder fan-out + copy

**Epic:** epic-notifications-meal-reminders
**Status:** done
**Date:** 2026-04-22

## Summary

Adds the Celery beat task that actually fires `MEAL_EVENT_REMINDER`
pushes, plus the shared fan-out helper and notification-copy variants.
This is what makes the "Remind me at" preference a real thing instead
of a column.

## Changes

**New** `libraries/utils/utils/services/meal_event_notifications.py`:
- `notify_meal_event_reminder(meal_event, db_session, now)` — resolves
  accepted participants (+ owner fallback), dedupes, calls the copy
  library per-recipient, sends via `PushNotificationService`. Per-
  recipient category prefs + quiet hours apply. One bad recipient
  doesn't kill the batch.
- `notify_meal_event_updated(...)` — also exported here for meal-4.
  Filters the actor out of fan-out; picks the copy variant based on
  whether only `scheduled_at` changed.

**New** `libraries/utils/utils/tasks/meal_event_tasks/send_meal_reminders.py`:
- `SendMealRemindersTask` (Celery `BaseTask`) registered as
  `send_meal_reminders`.
- SQL pre-filter: events with `scheduled_at` in [now-1d, now+1d+5min],
  not in `completed/skipped`, and either NULL `last_reminder_sent_at`
  or older than `now`.
- Python `_should_fire` applies the per-event logic: terminal status
  skip, resolved reminder moment in the [now, now+5min] window,
  dedupe gate.
- Timezone resolution: owner's `notification_preferences.timezone`
  (falls back to UTC on any error). DST is the OS's problem.
- After each successful fan-out, stamps `last_reminder_sent_at = now`
  and commits. A raise rolls back the row and writes an
  `error_logs` row with `service="push_notifications"`,
  `error_type="MealReminderTaskError"`; batch continues.

**Modified** `libraries/utils/utils/services/celery.py`:
- New `send-meal-reminders` beat schedule entry, every 5 minutes
  (`crontab(minute='*/5')`). Cadence MUST equal the task's
  `BEAT_WINDOW_SECONDS` so resolved moments are hit exactly once.

**Modified** `libraries/utils/utils/services/notification_copy.py`:
- `meal_event_reminder(meal_type, recipe_name, minutes_until,
  is_shared, partner_name)` — slot-label + emoji + optional
  "in N" prefix; snack slot uses 🥨. Returns `(title, body)` per
  the module contract.
- `meal_event_updated(actor_name, event_title, scheduled_at_changed,
  new_time)` — two variants (time-specific vs generic).

**Category mapping** in `push_notification.py`: already maps
`MEAL_EVENT_INVITE`, `MEAL_EVENT_REMINDER`, `MEAL_EVENT_UPDATED` →
`"meals"`. No change needed.

## Tests

- `libraries/utils/test/test_meal_event_notifications.py` — 11 tests
  covering solo / shared / declined-filter / owner-fallback / category
  suppression / exception resilience / "minutes until" formatting.
- `libraries/utils/test/test_send_meal_reminders.py` — 11 tests for
  the task: owner-timezone resolution (valid / missing / invalid),
  reminder-moment resolution (override vs slot default), window gates
  (inside / outside / terminal / already-sent), and two integration
  tests covering the full `execute()` loop including the
  one-bad-event-doesn't-kill-batch path.

## QA walkthrough

See `meal-3-celery-beat-meal-reminder-fanout-copy-qa-walkthrough.md`.
