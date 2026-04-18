# Story cal-share-5: Profile Shared Calendars + invitations-screen calendar invite UX

Status: ready-for-dev

## Story

As Leo,
I want a low-prominence Profile surface listing the calendars I'm an editor on (but don't own),
plus a clear calendar-invite card in my invitations inbox that lands me on the right calendar after I accept,
so that all the "where do I manage shared stuff?" surfaces have complete coverage.

## Acceptance Criteria

1. New `SharedCalendarsScreen` at route `/profile/shared-calendars`. Shows a flat list of calendars where `userRole == 'editor'` (i.e. shared with me, not owned by me). Empty state copy: "No shared calendars yet. When someone invites you to their calendar, it'll show up here."
2. Each row shows: calendar name, "Shared by …" subtitle (owner display name), trailing member count. Tap navigates to `/calendar/:id/members?role=editor&name=<calendar-name>` (the screen from cal-share-4).
3. Profile screen gains a new tile in the "My Stuff" / "Edit Profile" section: "Shared Calendars" → opens the new screen. Shows a small badge with the count when > 0.
4. `InvitationsScreen` already renders generic invitation cards (subject + accept/decline). Verify the calendar invitation rendering path picks up `resource_name` correctly. Add a calendar-specific copy for the subtitle: "Join calendar 'X' as editor" instead of the generic "Join 'X' as editor".
5. On Accept of a calendar invite: after the existing accept call succeeds, **explicitly call `activeCalendarProvider.setActive(resource_id)`** (per epic AC #5) and `ref.invalidate(calendarsListProvider)`, then snackbar "You joined [name]".
6. Widget tests: shared-calendars-screen renders empty state when no editor-role calendars; renders rows when present; tap navigates.

## Implementation Notes

- `CalendarService.listCalendars()` already returns every calendar the user is an active member of. Filter on `userRole == 'editor'` client-side for the SharedCalendarsScreen.
- The InvitationsScreen is currently a `StatefulWidget` (not Consumer). Convert to ConsumerStatefulWidget to get access to ref / providers (so we can call `activeCalendarProvider.setActive` from accept).
- Profile shared-calendars row: cheapest implementation is an unconditional row that always navigates; the count badge is an optimization. Use a FutureBuilder for the badge — small enough to inline.

## Tasks / Subtasks

- [x] **Task 1 — `SharedCalendarsScreen`** (AC: 1, 2)
  - [x] Create `app/lib/features/profile/shared_calendars_screen.dart`.
  - [x] Loads calendars via `CalendarService.listCalendars()`, filters editor-role.
  - [x] Renders rows + empty state.

- [x] **Task 2 — Router wiring** (AC: 1)
  - [x] Add `/profile/shared-calendars` GoRoute pointing at SharedCalendarsScreen.

- [x] **Task 3 — Profile tile** (AC: 3)
  - [x] Add "Shared Calendars" tile to Profile in the appropriate section.

- [x] **Task 4 — Invitations screen calendar branch** (AC: 4, 5)
  - [x] Convert InvitationsScreen to ConsumerStatefulWidget.
  - [x] On accept, dispatch on resource_type — calendar invites trigger setActive + calendars list invalidation.
  - [x] Subtitle: render "Join calendar 'X' as editor" for calendar resource_type.

- [x] **Task 5 — Tests** (AC: 6)
  - [x] Widget test for SharedCalendarsScreen empty state and populated list.

- [x] **Task 6 — Local CI**
  - [x] `flutter analyze lib/features/profile/ lib/features/invitations/`
  - [x] `flutter test test/features/`

### Key Files
- Create: `app/lib/features/profile/shared_calendars_screen.dart`
- Modify: `app/lib/core/router/app_router.dart`
- Modify: `app/lib/features/profile/profile_screen.dart`
- Modify: `app/lib/features/invitations/invitations_screen.dart`
- Create: `app/test/features/profile/shared_calendars_screen_test.dart`
