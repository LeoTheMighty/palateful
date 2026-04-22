# QA walkthrough — meal-3

Story: `meal-3-celery-beat-meal-reminder-fanout-copy` (epic
`notifications-meal-reminders`).

## Primary dogfood path

- [ ] Leo picks a recipe and plans a meal for **now + 2 minutes**
      (Lunch slot on a Tuesday, say).
- [ ] Within ~5 minutes (next beat tick), Leo's phone receives a push:
      title reads "Lunch in N — {Recipe} 🍳", body "Tap to open and
      start prepping.", recipe image attached.
- [ ] Tap → `/calendar/meals/{event_id}` detail screen (Epic A).

## Shared-meal fan-out

- [ ] Sarah creates a shared meal with Leo as a participant; Leo
      accepts.
- [ ] At the reminder time, BOTH phones get the push. Sarah's body
      reads "Leo is also cooking — tap to coordinate." Leo's body
      names Sarah.
- [ ] Add a third participant who declined the invite → still only 2
      pushes.

## Per-recipient suppression

- [ ] In Sarah's Profile → Notifications, toggle "Meals" category
      off. Create a fresh reminder.
- [ ] At the reminder time, Leo still gets the push; Sarah doesn't.

## Quiet hours

- [ ] Set Leo's quiet hours to cover the reminder minute (e.g. 22:00
      – 08:00 for a 23:00 meal). Fire the reminder.
- [ ] Leo's phone: no push (suppressed). Leo sees nothing on the lock
      screen.

## Idempotency

- [ ] Inspect `meal_events.last_reminder_sent_at` post-fire: populated
      with a UTC timestamp inside the 5-min window.
- [ ] Bounce the beat worker to re-run the task immediately. No
      second push fires (gate holds).

## Timezone correctness

- [ ] Create a meal as a user whose `notification_preferences.timezone`
      is "America/Los_Angeles", `scheduled_at=2026-05-02 12:00 PDT`,
      `meal_reminder_time = null` (slot default is 12:00). At 12:00
      Pacific, reminder fires. (Verify by running the task manually
      at 19:00 UTC.)

## Error path

- [ ] Cause one event in a batch to fail (mock `notify_meal_event_
      reminder` to raise for a specific `event.id`). Confirm:
      - Other events in the batch still get pushes.
      - `error_logs` has a new row with
        `error_type="MealReminderTaskError"`,
        `service="push_notifications"`, and the event id in the body.
      - That event's `last_reminder_sent_at` stays NULL (so it'll
        retry next tick).

## Not in scope

- Updated-event push (meal-4).
- Meal-detail reminder-row UI (meal-5).
