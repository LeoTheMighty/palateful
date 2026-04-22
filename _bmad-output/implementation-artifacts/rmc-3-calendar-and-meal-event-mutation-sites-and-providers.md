# rmc-3 — Calendar + meal-event mutation sites + list providers

**Status**: done
**Epic**: epic-reactive-migration-meals-calendar

## What shipped

`CalendarService` now emits on every CRUD write (`CalendarCreated`, `CalendarUpdated`, `CalendarDeleted`). `MealCalendarService` emits on every meal-event and recurrence-rule mutation. `markMealCompleted` signature upgraded from `Future<void>` to `Future<MealEvent>` — the endpoint already returned the full event; the method now actually returns it and emits `MealEventCompleted(event)` with the payload so subscribers patch in place (AC #3).

Three new providers live in `app/lib/features/calendar/providers/meal_events_provider.dart`:

- `mealEventsByRangeProvider((start, end, calendarId))` — range-containment filter + 100ms subscriber coalescer.
- `mealEventsByDayProvider((date, calendarId))` — exact-day-match filter + same coalescer.
- `upcomingEventsForMealProvider(mealId)` — mealId filter; future-window fetch.

All three subscribe to `MealEvent*` + `RecurrenceRule*` events and invalidate through a dedicated `Timer`-based 100ms debounce (coalescer helper extraction lands in rmc-4).

`calendar_screen.dart` refactored from an imperative `_loadEvents() + _eventsByDay + _loadGeneration + _isLoading` cluster to `ref.watch(mealEventsByRangeProvider(...))`. Deleted methods / fields: `_loadEvents`, `_loadGeneration`, `_isLoading`, `_error`, `_errorDetail`, `_eventsByDay`. The optimistic-undo flow for unschedule is now expressed as a `_pendingDeleteIds` set filtered at group-by time, so the 3-second undo window reuses the provider's source-of-truth list without mutating it. Child-sheet callbacks (`onEventsChanged`, `_loadEvents()` calls from `_openQuickAdd`, etc.) are gone — the service-layer emit drives invalidation.

`day_detail_sheet.dart` converted to `ConsumerWidget` + consumes `mealEventsByDayProvider` — no parent callback for refresh, no `events: List<MealEvent>` parameter.

`plan_meal_sheet.dart` failure path routes through `showMutationFailureSnackbar` with the correct `MutationType` per mode (edit → `rescheduleMealEvent`, recurrence → `createRecurrenceRule`, single → `planMealEvent`).

## Files

- `app/lib/core/state/mutation_event.dart` — added `CalendarDeleted`, `MealEventCompleted`, `MealEventDeleted`, `RecurrenceRuleCreated/Updated/Deleted`. New `MutationCategory.recurrenceRule`. Existing stubs (`MealEventArchived`, `CalendarArchived`, `MealEventCreated/Updated`) untouched — subscribers use the new types.
- `app/lib/core/state/mutation_failure_copy.dart` — added 15 new enum cases + copy entries: `createCalendar`, `updateCalendar`, `deleteCalendar`, `createMealEvent`, `updateMealEvent`, `rescheduleMealEvent`, `moveMealEvent`, `deleteMealEvent`, `markMealCompleted`, `planMealEvent`, `loadShoppingLists`, `addEventIngredients`, `createRecurrenceRule`, `updateRecurrenceRule`, `deleteRecurrenceRule`, `moveRecurrenceRule`.
- `app/lib/features/calendar/services/calendar_service.dart` — emits on create/update/delete.
- `app/lib/features/calendar/services/meal_calendar_service.dart` — emits on create / update / reschedule / move / delete / markCompleted / recurrence create-update-delete. `markMealCompleted` now `Future<MealEvent>`. `deleteMealEvent` gained `{String? calendarId}` so the deleted-event provider filter can be scoped.
- `app/lib/features/calendar/providers/active_calendar_provider.dart` — `calendarsListProvider` subscribes to `CalendarCreated | CalendarUpdated | CalendarDeleted | CalendarArchived`.
- `app/lib/features/calendar/providers/meal_events_provider.dart` — **new**. Three providers + inline coalescer.
- `app/lib/features/calendar/calendar_screen.dart` — big rewrite (~930 → ~710 lines). Grid driven by provider; `_pendingDeleteIds` for optimistic-undo.
- `app/lib/features/calendar/widgets/day_detail_sheet.dart` — `StatelessWidget` → `ConsumerWidget`; consumes `mealEventsByDayProvider`.
- `app/lib/features/calendar/widgets/plan_meal_sheet.dart` — failure path through `showMutationFailureSnackbar`.
- `app/test/features/calendar/calendar_grid_event_reactivity_test.dart` — **new** (rmc-3 AC #10).
- `app/test/features/calendar/day_sheet_reactivity_test.dart` — **new** (rmc-3 AC #11).
- `app/test/features/calendar/plan_meal_sheet_failure_snackbar_test.dart` — **new** (rmc-3 AC #12).
- `app/test/features/calendar/meal_autocomplete_field_test.dart` — mock signature fix for rmc-1 bookId-required changes on MealService (drive-by compile fix).
- 6 test files (`calendar_screen_test.dart`, `plan_meal_sheet_test.dart`, `meal_detail_sheet_recurring_test.dart`, `add_ingredients_from_calendar_test.dart`, `per_meal_shopping_add_test.dart`, `recurring_plans_screen_test.dart`) — mock `markMealCompleted` signature bumped to `Future<MealEvent>`; `deleteMealEvent` mocks updated to `{String? calendarId}`.
- `add_ingredients_from_calendar_test.dart` + `per_meal_shopping_add_test.dart` — failure-snackbar text migrated from "Failed to add ingredients" → "Couldn't add ingredients" (new `MutationType.addEventIngredients` copy).

## Gotchas

- **MealEvent model does not carry `calendarId`.** The DTO never parsed it. Event-level filters in `meal_events_provider.dart` extract calendar_id from the raw payload map (`event.event['calendar_id']`) rather than the typed model. Cheap and avoids a model migration.
- **MealEventDeleted carries optional `calendarId`.** The service emits it from the caller-supplied arg in `calendar_screen.dart._unscheduleWithUndo`. Providers treat `null` as "unknown → invalidate to be safe" (can't prove out-of-scope). Good enough for the single-user case.
- **Optimistic undo rewritten.** The pre-refactor approach mutated `_eventsByDay` directly on unschedule tap + restored it on Undo. With the provider as the source of truth, mutating it would require patching AsyncData twice. The new approach: a `_pendingDeleteIds` set the widget applies at group-by time — delete happens in the provider's data only after the undo window expires and the service call completes (which invalidates via `MealEventDeleted`).
- **100ms coalescer inlined, not yet extracted.** Three copies of the Timer+debounce pattern in `meal_events_provider.dart`. rmc-4 extracts to a `MealEventCoalescer` helper.
- **Non-error loading state no longer shows a spinner.** Pre-refactor the body flipped to `CircularProgressIndicator` while `_isLoading = true`. New behavior: render the 7 day columns immediately with an empty grid; let the provider fill in when data arrives. Matches the existing day-columns-render-first test expectation in `calendar_screen_test.dart` and avoids a skeleton flash on every invalidation.
- **Widget viewport 1080×2400 for tests.** Reactivity tests that assert on text below the fold set `tester.view.physicalSize = Size(1080, 2400)` so the third and lower rows are visible. Default 800×600 pushes them off-screen.

## QA walkthrough

### Regression (CI-guarded)

- [x] `calendar_grid_event_reactivity_test.dart` — `MealEventCreated` in range triggers refetch (listCalls increments), new tile appears. 100ms coalescer settles.
- [x] `day_sheet_reactivity_test.dart` — `DayDetailSheet` re-renders when a new event lands on the visible day.
- [x] `plan_meal_sheet_failure_snackbar_test.dart` — `createMealEvent` throws → `MutationType.planMealEvent` copy shown, sheet stays open.
- [x] All 115 existing calendar tests pass.
- [x] All 331 tests across meals/ + calendar/ + core/ pass.

### Manual dogfood (end-to-end — deferred to rmc-5)

- [ ] Calendar → tap Friday → plan "Sunday Roast" at 6:30 PM → cell renders new chip without reload; day-sheet list contains the event.
- [ ] Mark event as cooked → cell chip re-renders with `status=completed` visible on the row (cooked indicator). `_loadEvents()` removed; no manual refresh.
- [ ] Unschedule a meal → optimistic removal → Undo restores; no Undo → 3s later the event disappears (and subsequent Create reappears via the bus, not via local setState).
- [ ] Create a new calendar in the switcher header → calendar list updates without reload.
- [ ] Delete a calendar in settings → switcher header updates, active-id fallback resolves, grid reloads for the new active id.
