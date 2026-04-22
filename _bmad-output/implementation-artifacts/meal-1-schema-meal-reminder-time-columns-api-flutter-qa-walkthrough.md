# QA walkthrough — meal-1

Story: `meal-1-schema-meal-reminder-time-columns-api-flutter` (epic
`notifications-meal-reminders`).

meal-1 is a schema / plumbing story — no user-visible UI. QA here is
API-level:

## API round-trip

- [ ] `POST /v1/meal-events` with `"meal_reminder_time": "11:45"` →
      response includes `meal_reminder_time: "11:45:00"` and
      `reminder_time: "11:45:00"`.
- [ ] `POST /v1/meal-events` without that key → response has
      `meal_reminder_time: null` and `reminder_time` populated with the
      slot default (lunch → `"12:00:00"`, dinner → `"18:30:00"`,
      breakfast → `"08:00:00"`, snack → `"15:00:00"`).
- [ ] `PUT /v1/meal-events/{id}` with `"meal_reminder_time": "11:45"` →
      persists, response echoes override, and `last_reminder_sent_at`
      is not changed.
- [ ] `PUT /v1/meal-events/{id}` with `"meal_reminder_time": null` →
      clears the override, response shows `meal_reminder_time: null`
      and `reminder_time` falls back to slot default.
- [ ] `PUT /v1/meal-events/{id}` **without** the key → column is
      unchanged (omit ≠ null).
- [ ] `POST /v1/meal-events` with `"meal_reminder_time": "not-a-time"`
      → 422.

## DB

- [ ] Migration applies cleanly: run `npx nx run migrator:migrate` on a
      dev DB and confirm both columns + the composite index exist.
- [ ] Downgrade works: `alembic downgrade -1` drops columns + index.

## Flutter model

- [ ] `MealEvent.fromJson` parses `meal_reminder_time` as "HH:MM" (the
      `_parseTimeString` helper trims the trailing seconds).
- [ ] Field is null for events created before this migration (legacy
      rows round-trip safely).

## Not in scope

- No Remind-me-at picker UI yet (meal-2).
- No scheduler fires (meal-3).
- No MEAL_EVENT_UPDATED fan-out (meal-4).
