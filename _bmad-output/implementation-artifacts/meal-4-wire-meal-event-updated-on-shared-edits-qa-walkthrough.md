# QA walkthrough — meal-4

Story: `meal-4-wire-meal-event-updated-on-shared-edits` (epic
`notifications-meal-reminders`).

## Primary path

- [ ] Sarah creates a shared meal with Leo as a participant (Saturday
      brunch, 11:00 AM). Leo accepts.
- [ ] Sarah moves the meal to 12:30 PM via the edit flow.
- [ ] Leo's phone gets a push: title **"Saturday brunch moved to
      12:30 PM"**, body **"Sarah updated 'Saturday brunch'"**. Tap →
      meal detail screen.

## Copy variants

- [ ] Sarah changes ONLY `scheduled_at` → time-specific title (moved
      to).
- [ ] Sarah changes `title` AND `scheduled_at` → generic title
      (**"{event} updated"**), generic body.
- [ ] Sarah changes `recipe_id` → generic variant fires.
- [ ] Sarah changes `meal_reminder_time` → generic variant fires.

## Actor exclusion

- [ ] Sarah is the one who made the edit — she does NOT get a push.
- [ ] Every other accepted participant DOES (Leo + anyone else who
      RSVP'd yes).
- [ ] A participant who declined the invite is skipped.

## Non-triggers

- [ ] Sarah changes only the description → no push.
- [ ] Sarah changes `notify_prep_start` / `prep_start_offset_minutes`
      → no push.
- [ ] A non-shared meal's title change → no push (no co-cooks).

## Robustness

- [ ] Simulate a push-service outage while Sarah edits a shared meal
      (e.g. disable Firebase creds). The PATCH still returns 200,
      the edit persists, and an `error_logs` row records the
      fan-out failure. No user-facing error.

## Not in scope

- The older `api.v1.meal_event.utils.notifications.notify_meal_event_
  updated` stub still exists for legacy tests — meal-4 does NOT use
  it; we go through the shared `utils.services.meal_event_notifications`
  module.
