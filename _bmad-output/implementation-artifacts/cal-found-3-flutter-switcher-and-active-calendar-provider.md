# Story cal-found-3: Flutter calendar switcher + active-calendar provider

Status: ready-for-dev

## Story

As Leo,
I want a header picker on the Calendar tab so I can see which calendar I'm looking at and swap between them in two taps,
so the multi-calendar UX is navigable.

## Acceptance Criteria

1. `Calendar` model at `app/lib/features/calendar/models/calendar.dart` with fields matching the backend `CalendarResponse` (id, name, description, isDefault, isShared, ownerId, userRole, memberCount, createdAt, updatedAt).
2. `CalendarService` at `app/lib/features/calendar/services/calendar_service.dart` wrapping `ApiClient` calls for `listCalendars`, `createCalendar`, `getCalendar`, `updateCalendar`, `deleteCalendar`. `ApiClient` gains methods for `/v1/calendars` CRUD.
3. `activeCalendarProvider` at `app/lib/features/calendar/providers/active_calendar_provider.dart` — Riverpod `AsyncNotifierProvider` exposing the currently-selected calendar id.
   - `build()` returns the persisted id from `shared_preferences` if it's present in the latest `listCalendars()` response; otherwise falls back to the user's `is_default=true` calendar; surfaces an error state "Calendars unavailable, retry" if the list is empty (impossible post-backfill, defensive).
   - `setActive(calendarId)` persists the new id and emits the new state.
   - `clearInvalid()` removes the stored id, re-reads the list, falls back to default. Intended for 404-on-list-refresh scenarios.
4. `CalendarSwitcherHeader` at `app/lib/features/calendar/widgets/calendar_switcher_header.dart` — a `ConsumerWidget` chip showing the active calendar's name + chevron-down. Full-width tappable; on tap opens `CalendarSwitcherSheet`.
5. `CalendarSwitcherSheet` at `app/lib/features/calendar/widgets/calendar_switcher_sheet.dart` — bottom sheet showing a list of calendars:
   - Each row: name, subtitle "Owned by you", active row checkmark.
   - Row body tap → `activeCalendarProvider.setActive(calendarId)` + dismiss.
   - Trailing chevron on each row → opens `CalendarSettingsSheet` (cal-found-4 ships the sheet; in this story, stub the handler as `onOpenSettings(calendar)` callback — wired to a no-op for now).
   - "Shared with Me" section exists in the tree but `Visibility(visible: false)` — flipped on in the sharing epic.
   - Footer: `+ New Calendar` action — stub callback `onCreateCalendar` (cal-found-4 wires it).
6. `CalendarPickerSheet` at `app/lib/features/calendar/widgets/calendar_picker_sheet.dart` — extracted reusable widget that `CalendarSwitcherSheet` wraps. Shows the same list + onSelect callback. Reused by cal-found-5's plan-meal Calendar row picker.
7. `calendar_screen.dart`:
   - Swap the static `_buildWeekNavigator` title for `CalendarSwitcherHeader` + retains the week nav as the subtitle/row below the header.
   - Convert `CalendarScreen` to `ConsumerStatefulWidget` (per epic principle #4 — minimal Riverpod adoption, don't migrate the whole grid).
   - `_loadEvents` reads the active id from the provider and passes it as `calendar_id` to the list API.
   - Reload events on provider change via `ref.listen(activeCalendarProvider, ...)`.
   - Empty-state copy: "No meals on [active calendar name] yet. Tap + to plan one."
8. `MealCalendarService.listMealEvents` accepts an optional `calendarId` parameter and passes it as `calendar_id` query param to `/v1/meal-events`.
9. Widget tests in `app/test/features/calendar/`:
   - `active_calendar_provider_test.dart`: build with 1 / 3 calendars, persistence via mocked SharedPreferences, fallback-to-default when stored id is invalid, clearInvalid behavior.
   - `calendar_switcher_test.dart`: render with 1 / 3 calendars, row-tap activates, chevron-tap fires the settings callback (distinct hit targets), checkmark on active row.

## Tasks / Subtasks

- [ ] **Task 1 — Calendar model + service**
  - [ ] Create `models/calendar.dart` with `Calendar` class + `fromJson`.
  - [ ] Add `/v1/calendars` methods to `ApiClient`: `listCalendars()`, `createCalendar(name, description?)`, `getCalendar(id)`, `updateCalendar(id, {name?, description?})`, `deleteCalendar(id)`.
  - [ ] Create `services/calendar_service.dart` wrapping `ApiClient`.

- [ ] **Task 2 — Active-calendar provider**
  - [ ] Create `providers/active_calendar_provider.dart`:
    - `AsyncNotifierProvider<ActiveCalendarNotifier, String?>` exposing the active id.
    - Uses `SharedPreferences` for persistence (key: `active_calendar_id`).
    - `build()` reads from storage, verifies against `CalendarService.listCalendars()`, falls back to `is_default=true`.
    - `setActive(id)`, `clearInvalid()` methods.
    - Exposes a companion `calendarsListProvider` (FutureProvider) that caches the list result — switcher sheet reads this without re-fetching.

- [ ] **Task 3 — Switcher UI widgets**
  - [ ] `CalendarPickerSheet` (reusable): renders the calendar list with `onSelect` callback, shows active-row highlight. Separate row body + trailing chevron hit targets with `onOpenSettings` callback (forwarded).
  - [ ] `CalendarSwitcherSheet` wraps `CalendarPickerSheet` + `+ New Calendar` footer.
  - [ ] `CalendarSwitcherHeader` — ConsumerWidget chip showing active calendar name + chevron-down; tap opens switcher sheet.

- [ ] **Task 4 — Calendar screen integration**
  - [ ] Convert `CalendarScreen` → `ConsumerStatefulWidget`.
  - [ ] Replace app-bar title `_buildWeekNavigator` with `CalendarSwitcherHeader` + keep week nav row BELOW the header.
  - [ ] `_loadEvents` passes the active calendar id as `calendar_id` to `MealCalendarService.listMealEvents`.
  - [ ] `ref.listen(activeCalendarProvider, ...)` → `_loadEvents()` when the id changes.
  - [ ] Empty-state rendering uses the active calendar's name.

- [ ] **Task 5 — MealCalendarService wiring**
  - [ ] `listMealEvents(start, end, {calendarId})` adds `calendar_id` query param when non-null.
  - [ ] `ApiClient.listMealEventsForRange(start, end, {calendarId})` passes through.

- [ ] **Task 6 — Tests**
  - [ ] `app/test/features/calendar/active_calendar_provider_test.dart` — stub SharedPreferences + CalendarService, verify persistence / fallback / clearInvalid.
  - [ ] `app/test/features/calendar/calendar_switcher_test.dart` — golden-path switcher render + tap interactions.

- [ ] **Task 7 — Local CI**
  - [ ] `flutter analyze lib/features/calendar/` clean.
  - [ ] `flutter test test/features/calendar/` passes.

## Dev Notes

- **Scoping Riverpod**: per epic principle #4, only the active-calendar state is Riverpod in this story. The calendar grid keeps `StatefulWidget` + plain services. The switch: convert `CalendarScreen` to `ConsumerStatefulWidget` so the build method has `ref`, but keep `_loadEvents` / `_eventsByDay` as State.

- **Persistence key**: `active_calendar_id`. No prefix; the app has no namespacing convention.

- **`CalendarPickerSheet` reuse contract**: Accepts `{required List<Calendar> calendars, required String? activeId, required ValueChanged<Calendar> onSelect, ValueChanged<Calendar>? onOpenSettings}`. No default styling for active-row highlight — callers pass a boolean per-row.

- **Error state**: `activeCalendarProvider` returns `AsyncValue<String?>` — the `null` case only occurs on initial load before list resolves. On list-fetch failure, state transitions to `AsyncError`; `CalendarSwitcherHeader` shows "Calendars unavailable" + retry.

- **QA walkthrough**: output to `cal-found-3-qa-walkthrough.md`.

### References

- [Source: _bmad-output/planning-artifacts/epic-calendars-foundation.md#Story cal-found-3]
- Existing patterns: `app/lib/features/chat/chat_provider.dart` (Riverpod pattern), `app/lib/providers/theme_mode_provider.dart`.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### File List
