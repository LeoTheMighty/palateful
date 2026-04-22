# QA walkthrough — meal-2

Story: `meal-2-frontend-remind-me-at-time-picker` (epic
`notifications-meal-reminders`).

## Happy path

- [ ] From the calendar, tap "+ Plan a meal". The picker sheet opens.
- [ ] Pick a recipe → pick a date → tap "Lunch" chip. The "Remind me
      at" row shows **12:00 PM** with a greyed-out **"Lunch default"**
      caption.
- [ ] Tap the row. Material time picker opens at 12:00 PM. Set it to
      11:45 AM and confirm. The row now reads **11:45 AM**, the
      caption is gone, and a small "Reset to default" link appears
      above the row.
- [ ] Save the meal. Pull the meal back up in the detail screen (or
      inspect the API response): `meal_reminder_time` is `"11:45:00"`.

## Meal-type switches

- [ ] With NO override set: tap Breakfast → row reads 8:00 AM; tap
      Dinner → 6:30 PM; tap Snack → 3:00 PM. Caption updates per slot.
- [ ] Set an override to 10:00 AM, then switch meal type from Lunch to
      Dinner. Row still reads **10:00 AM** — override wins; the caption
      stays hidden.
- [ ] Tap **Reset to default** → row reverts to the current slot
      default (e.g., Dinner → 6:30 PM), caption returns.

## Save semantics

- [ ] Save with no override → request payload to `/v1/meal-events`
      **omits** `meal_reminder_time` (backend resolves to slot default).
- [ ] Save with override `11:45 AM` → payload includes
      `"meal_reminder_time": "11:45"`.

## Edge

- [ ] Time picker respects device locale — 24h clock when the OS is in
      24h mode.
- [ ] In edit mode (`eventId` provided), the picker row is present and
      round-trips the current value.

## Not in scope

- Scheduler doesn't fire yet (meal-3).
- Meal detail screen still shows the old UI — reminder-row there is
  meal-5.
