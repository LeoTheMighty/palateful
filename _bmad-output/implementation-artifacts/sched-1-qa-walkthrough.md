# QA Walkthrough — sched-1 (Shopping Deadline Reminders)

## Automated regression (already passing)

- [x] `services/api/tests/test_shopping_notifications.py` — 10 tests covering copy helpers (`shopping_deadline_reminder`, `import_failed`) and `notify_shopping_deadline_reminder` behavior.
- [x] `services/api/tests/test_send_shopping_deadline_reminders.py` — 16 tests covering the beat-task scenarios A–G from the epic plus helper-level unit tests, empty-tick no-op, and per-user exception isolation.

## Manual smoke

Run on the staging worker (or by kicking the task manually in a dev shell):

1. **Happy path (solo list).**
   - Create a shopping list named "Weekend BBQ".
   - Add 3 items with `due_at = today 18:00` in your own tz; leave unchecked.
   - Ensure `notification_preferences.timezone` on your user row matches your wall-clock tz (defaults to `America/Denver` for fresh accounts).
   - Wait for the next 08:00 (±5 min) beat tick, or invoke the task manually:
     ```
     docker compose exec worker python -c \
       "from utils.tasks.shopping_list_tasks.deadline_reminder_task import deadline_reminder_task; print(deadline_reminder_task.delay().get())"
     ```
   - ✅ Expect: one push ("🛒 3 items on Weekend BBQ are due today") to arrive on your device.
   - ✅ Expect: new row in `shopping_list_user_reminder_state` with your `user_id`, the list's `id`, and `last_deadline_reminder_sent_at` in UTC.

2. **Idempotency.**
   - Run the task again within the 08:00–08:05 window same morning.
   - ✅ Expect: no second push.
   - Query: the state row's `last_deadline_reminder_sent_at` is unchanged.

3. **Checked items ignored.**
   - Check off all 3 items, then run the task.
   - ✅ Expect: no push (even on the next morning).

4. **Tomorrow items ignored.**
   - Add an item due tomorrow and no items due today, then run the task.
   - ✅ Expect: no push today.

5. **Out-of-window.**
   - Run the task at 09:00 local. (The task still fires but should no-op.)
   - ✅ Expect: no push; task logs "tick complete users=0 pushes=0".

6. **Category opt-out.**
   - Toggle `notification_preferences.categories.shopping = false`.
   - Add due-today items, run task at 08:02 local.
   - ✅ Expect: `notify_shopping_deadline_reminder` still fires; the push service suppresses
     (`suppressed_by_category=true` in logs); device sees no push.

7. **Shared list, two timezones (critical).**
   - Invite Sarah (pretend user in EST) to Leo's (MST) Weekend BBQ list. Both users have due-today items.
   - At 12:02 UTC: only Sarah gets the push.
   - At 14:02 UTC: only Leo gets the push.
   - ✅ Expect: two distinct `shopping_list_user_reminder_state` rows, each with that morning's
     timestamp. Neither push suppressed the other.

## Rollback notes

- Task name is unchanged (`shopping_list_deadline_reminder`), so rollback = revert the commit.
- Migration `schdrem001` is reversible (`alembic downgrade -1` drops the new table). No other tables are touched.
- Beat schedule swap (`crontab(minute='*/5')` vs `900.0`) is a no-op at runtime — the task short-circuits if no tz is in window.

## Known non-blocking notes

- `migrator:check-models` locally reports drift on `ix_meal_events_reminder_scan` — that's a parallel-agent WIP (`mealrmndrflds01` migration creates the index but the model hasn't been updated yet). CI on a clean checkout will pass.
- Users with `notification_preferences.timezone` unset are skipped entirely. Onboarding writes a default tz so this should only hit legacy accounts.
