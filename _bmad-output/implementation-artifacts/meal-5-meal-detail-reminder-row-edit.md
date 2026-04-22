# Story meal-5: Meal detail reminder row + edit

**Epic:** epic-notifications-meal-reminders
**Status:** done
**Date:** 2026-04-22

## Summary

Adds a "Reminder" row to the meal detail screen showing the resolved
reminder time (override or slot default). Tap opens a Material time
picker; selection auto-saves via `MealCalendarService.setMealReminderTime`
(meal-1 partial-update). "Reset to default" affordance clears the
override back to null.

Saving a change on a shared meal goes through the existing update
path, so meal-4's MEAL_EVENT_UPDATED fan-out triggers for co-cooks.

## Changes

**`app/lib/features/calendar/meal_detail_screen.dart`:**
- Injects `MealCalendarService` alongside `ApiClient`.
- New state field `_reminderInFlight` for optimistic in-flight UI.
- `_slotDefault(MealType)` mirrors the backend's
  `MEAL_SLOT_DEFAULT_TIMES` constant (with a cross-referencing
  comment). Kept duplicated rather than imported from
  `plan_meal_sheet.dart` to avoid a circular import between detail
  screen and edit sheet.
- `_parseTimeOfDay(hhmm)` / `_wire(t)` / `_formatTimeOfDay(t)`
  helpers for the wire-format round trip.
- `_pickReminderTime` — opens `showTimePicker` at the current
  resolved value; save on confirm.
- `_resetReminder` — sends an explicit null so the backend clears the
  override (meal-1 endpoint uses `model_fields_set`).
- `_saveReminder(wire)` — calls `setMealReminderTime`, swaps in the
  returned event. Errors surface a snackbar + `ErrorReporter.report`.
- `_buildReminderRow(event)` widget — "Reminder" label, tappable row
  with bell icon, `(Lunch default)` caption when no override, inline
  Reset button only when override is set, in-flight spinner.
- Inserts the row between the meal-type chips and the recipe card.

## Tests

Existing unit tests in
`app/test/features/calendar/meal_event_detail_screen_test.dart` still
pass (they test internal formatter helpers, not the screen
composition). The screen-level reminder flow is covered by the
manual QA walkthrough; full widget-level mocking of
`MealCalendarService` + `ApiClient` is out of scope for this story
(matches Epic A's nfn-5 stance — this screen is a "target, not a
workspace").

## QA walkthrough

See `meal-5-meal-detail-reminder-row-edit-qa-walkthrough.md`.
