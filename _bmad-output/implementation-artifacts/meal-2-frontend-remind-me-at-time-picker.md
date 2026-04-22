# Story meal-2: Frontend "Remind me at" time picker

**Epic:** epic-notifications-meal-reminders
**Status:** done
**Date:** 2026-04-22

## Summary

Adds the "Remind me at" picker row to `plan_meal_sheet.dart`. Default
tracks the current slot (8/12/18:30/15); user can override per-meal via
a Material time picker; override persists across meal-type changes;
inline "Reset to default" clears back to null.

## Changes

**`app/lib/features/calendar/widgets/plan_meal_sheet.dart`:**
- `_mealReminderOverride: TimeOfDay?` state.
- `_effectiveReminderTime` getter — override-or-default.
- `_buildReminderRow` widget — label, tappable row, caption, reset
  button (only when override is set).
- `_pickReminderTime` / `_resetReminderToDefault` handlers.
- `_reminderTimeWire` formatter — serializes as "HH:MM" for the API.
- Bumped `_mealDefaultTime(dinner)` from `(18, 0)` → `(18, 30)` to
  match the backend's `MEAL_SLOT_DEFAULT_TIMES["dinner"]` (meal-1). The
  prior 18:00 was a silent drift from the epic spec.
- Cross-referencing comment points at the backend constant.
- `_save()` wires `mealReminderTime` into the create payload; null
  omits the key (backend falls back to slot default).

**Fakes in test files** — all existing `implements MealCalendarService`
fakes updated to add the new `mealReminderTime` optional kwarg on
`createMealEvent` and the new `setMealReminderTime` method stub:
- `app/test/features/calendar/plan_meal_sheet_test.dart` (fake also
  records `lastCreatedReminderTime`)
- `app/test/features/calendar/calendar_screen_test.dart`
- `app/test/features/calendar/meal_detail_sheet_recurring_test.dart`
- `app/test/features/calendar/per_meal_shopping_add_test.dart`
- `app/test/features/calendar/add_ingredients_from_calendar_test.dart`
- `app/test/features/profile/recurring_plans_screen_test.dart`

## Tests

In `plan_meal_sheet_test.dart`, new `PlanMealSheet — Remind-me-at
picker (meal-2)` group:

- Lunch slot → "12:00 PM" + "Lunch default" caption (AC 7 Test A)
- Dinner slot → "6:30 PM" + "Dinner default" caption (AC 7 Test B)
- Breakfast → "8:00 AM" + "Breakfast default" caption
- Switching meal type updates default when no override is set (AC 7 Test E+/folded)
- Save with no override → payload omits `meal_reminder_time` (AC 7 Test G)
- Reset-to-default button only visible with an override set

## QA walkthrough

See `meal-2-frontend-remind-me-at-time-picker-qa-walkthrough.md`.
