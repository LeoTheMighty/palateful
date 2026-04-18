# Story cal-found-5: Plan-meal Calendar row + Move-to-calendar

Status: done

## Story

As Leo, I want the plan-meal sheet to default to my active calendar and let me change destination per-meal, and I want to move an existing meal from one calendar to another without recreating it.

## What shipped

1. **`MealCalendarService`** sends `calendar_id` on every write (`createMealEvent`, `createRecurrenceRule`, optional on `updateMealEvent`). `moveMealEventToCalendar(eventId, newCalendarId)` + `moveRecurrenceRuleToCalendar(ruleId, newCalendarId)` helpers delegate the flip to the backend.
2. **PlanMealSheet** is now a `ConsumerStatefulWidget`. Form holds its own `_targetCalendarId`, seeded from `activeCalendarProvider` at open time; changing it never mutates the provider (principle #5).
3. **Calendar row** appears in the plan-meal form ABOVE the Date row — hidden entirely when the user has only one writable calendar (principle #11: no dead UI for the solo case).
4. Tapping the row opens **`CalendarPickerSheet`** (reused from cal-found-3) scoped to the user's owned calendars.
5. **MealDetailSheet** is now a `ConsumerStatefulWidget`. Adds a **Move to calendar** row in the secondary actions area — hidden when the user has only one writable calendar. Tap opens the picker, confirms ("Move 'X' to 'Y'?" — rule-level copy for recurring), and calls the appropriate backend endpoint.
6. Recurring Move is **rule-level**: `PATCH /recurrence-rules/{ruleId}` with the new `calendar_id`. Backend cascades to future materialized meal_events (cal-found-2 Task 10).
7. Tests: existing calendar + profile test fakes updated to the new `MealCalendarService` signature. Plan-meal and meal-detail sheet tests wrapped in `ProviderScope` for Riverpod access.

### References

- [Source: _bmad-output/planning-artifacts/epic-calendars-foundation.md#Story cal-found-5]
- Existing patterns: `CalendarPickerSheet` (cal-found-3), `moveMealEventToCalendar` endpoint (cal-found-2).
