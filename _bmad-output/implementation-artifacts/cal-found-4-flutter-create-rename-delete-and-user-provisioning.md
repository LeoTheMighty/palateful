# Story cal-found-4: Flutter create/rename/delete calendar + wire switcher

Status: ready-for-dev

## Story

As Leo, I want to create a new calendar, rename one, and delete ones I no longer need — plus trust that every user gets a default calendar on sign-up — so I can actually use the multi-calendar UX.

## Acceptance Criteria

1. `CalendarCreateDialog` (modal) with required name field (128-char max, autofocus) + optional multi-line description field. Create button disabled until name is non-empty.
2. Submitting → `CalendarService.createCalendar(name, description?)` → on success, new calendar becomes active via `activeCalendarProvider.setActive(newId)`, switcher sheet dismisses (caller owns this), grid reloads. On failure, dialog stays open + snackbar error.
3. `CalendarSettingsSheet` (bottom sheet): name field + explicit Save button (matches recipe-book precedent — not autosave-on-blur). Description field same pattern. Members section shows owner row + "Sharing coming soon" helper. Destructive **Delete calendar** button at the bottom.
4. Save → `updateCalendar(id, {name, description})`. Failure: inline error, stays editable. Save button disables during in-flight.
5. Delete prompts confirmation dialog: "Delete '[name]'? All meals on this calendar will be archived. This cannot be undone." (solo). Plural copy "Delete '[name]'? N members will lose access. All meals will be archived." is templated behind a `members > 1` check — activated naturally once the sharing epic ships.
6. On Delete: `deleteCalendar(id)` → dismiss settings sheet + switcher sheet → if the deleted id was active: fall back to the user's default; if default was the deletion target: fall back to most-recently-created remaining → reload the grid.
7. Deleting the user's **only** calendar is prevented at the UI level (Delete button disabled, helper: "You can't delete your only calendar"). Backend also enforces (400+261).
8. Switcher `+ New Calendar` footer and row chevrons are wired to the new sheets.
9. Widget tests: create-happy-path (new calendar becomes active), create-validation (empty name → Create disabled), rename-explicit-save, delete-last-calendar-forbidden, delete-propagates-to-active-fallback.
10. User-provisioning flow already landed in cal-found-1 (`_ensure_default_calendar` in `dependencies.py`). This story doesn't repeat that work — just verifies via Flutter integration that a fresh user's first app load shows exactly one default calendar.

## Tasks

- [ ] `CalendarCreateDialog` widget
- [ ] `CalendarSettingsSheet` widget (rename + description + delete + disabled "only calendar" state)
- [ ] Wire `CalendarSwitcherHeader`/`Sheet` callbacks in `calendar_screen.dart`
- [ ] Widget tests: `calendar_create_dialog_test.dart`, `calendar_settings_sheet_test.dart`

### References

- [Source: _bmad-output/planning-artifacts/epic-calendars-foundation.md#Story cal-found-4]
- Existing patterns: recipe-book settings screen for explicit Save pattern.
