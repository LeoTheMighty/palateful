# Story meal-1: Schema + API + Flutter model for meal reminder time

**Epic:** epic-notifications-meal-reminders
**Status:** done
**Date:** 2026-04-22

## Summary

Adds the schema + API surface + Flutter model for the per-meal
"Remind me at" wall-clock override. The column exists; the API
round-trips it; the Flutter model parses it. No UI yet (meal-2), no
scheduler yet (meal-3).

## Changes

**Migration** `20260422000000_add_meal_event_reminder_fields.py`:
- `meal_events.meal_reminder_time` (TIME, nullable)
- `meal_events.last_reminder_sent_at` (TIMESTAMPTZ, nullable)
- Index `ix_meal_events_reminder_scan` on `(scheduled_at,
  last_reminder_sent_at)` (concurrent) — supports the scheduler scan
  query meal-3 will write.

**Model** `libraries/utils/utils/models/meal_event.py`:
- `MEAL_SLOT_DEFAULT_TIMES` module constant (8:00 / 12:00 / 18:30 /
  15:00). Comment cross-references the Flutter constant.
- `meal_reminder_time` / `last_reminder_sent_at` columns.
- `reminder_time` property — returns the override or the slot default.

**Schemas + endpoints** `services/api/src/api/v1/meal_event/{create,update,get}_meal_event.py`:
- `Params.meal_reminder_time: time | None` on Create + Update.
- `Response.meal_reminder_time` (user's override, may be null) +
  `reminder_time` (resolved, always populated).
- Update handler uses `model_fields_set` to distinguish
  omitted-from-payload ("leave unchanged") from explicit null ("clear
  override, revert to slot default"). This is load-bearing for the
  meal-5 "Reset to default" affordance.

**Flutter** `app/lib/features/calendar/models/meal_event.dart`:
- `mealReminderTime: String?` (user's override, "HH:MM" or null).
- `reminderTime: String?` (resolved). Both parsed from the Pydantic
  "HH:MM:SS" wire format via a private `_parseTimeString` helper that
  trims seconds.

**Flutter service** `app/lib/features/calendar/services/meal_calendar_service.dart`:
- `createMealEvent` gains optional `mealReminderTime` kwarg.
- New `setMealReminderTime(eventId, reminderTime)` partial-update for
  the meal-5 detail-screen edit affordance. Sends JSON-null explicitly
  when clearing, so the backend's field-presence check fires.

## Tests

All new API tests live in `services/api/tests/test_meal_event.py`:

- `test_create_with_meal_reminder_time_persists_value` — AC 7 Test A
- `test_create_without_reminder_override_resolves_slot_default` — AC 7 Test B
- `test_create_with_invalid_reminder_time_string_is_422` — AC 7 Test D
- `test_update_meal_reminder_time_persists` — AC 7 Test C
- `test_update_meal_reminder_time_clear_via_explicit_null` — Reset-to-default path

## QA walkthrough

See `meal-1-schema-meal-reminder-time-columns-api-flutter-qa-walkthrough.md`.
