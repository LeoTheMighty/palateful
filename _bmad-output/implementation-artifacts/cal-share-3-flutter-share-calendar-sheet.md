# Story cal-share-3: Flutter Share Calendar sheet + Calendar Settings wire-up

Status: ready-for-dev

## Story

As Leo,
I want a Share action on the calendar I own that opens a sheet to invite by email/username or copy an invite link,
so that sharing is the same two-tap flow I already know from recipe books.

## Acceptance Criteria

1. `CalendarSettingsSheet` replaces its "Sharing coming soon" placeholder with a real Members section: lists active members + pending invitations (calls new `GET /calendars/{id}/members`). Owner sees a "Share Calendar" button at the bottom of the section. Editors do not see Share (read-only).
2. Tapping **Share Calendar** opens `ShareCalendarSheet` — a bottom sheet with two tabs: **Invite by email/username** (default) and **Share link**. Modeled after `_showInviteBottomSheet` in `recipe_book_members_screen.dart` — same pattern.
3. Invite by email/username: text field, fixed role indicator "Editor" (calendars only support editor), Send button. On send: `POST /v1/invitations` with `resource_type='calendar'`, `role_offered='editor'`, calendar id, and the entered target. Success → snackbar + sheet closes + member list refreshes. Error → snackbar with code-aware message (already-member, already-sent, self-invite).
4. Share link tab: Generate link button → `POST /v1/invite-links` with `resource_type='calendar'`, role `editor`. Returns the deep link `palateful://invite/{token}`. Copy button + native Share button.
5. `CalendarService` gets `listCalendarMembers(id)` returning the merged active+pending members list. Used by `CalendarSettingsSheet`.
6. Pull-to-refresh on the Members section reloads the list (calls listCalendarMembers).
7. Member-count in the parent switcher sheet refreshes when the settings sheet returns (existing `ref.invalidate(calendarsListProvider)` pattern after sharing actions).
8. Widget tests: settings-sheet renders members + share button; share sheet renders both tabs; send-invite-success path; send-invite-error-renders-message; create-link path; editor-sees-no-share-button.

## Implementation Notes

- All new code in `app/lib/features/calendar/`. Reuse the existing API client methods — they're parameterized by `resource_type`.
- The existing `CalendarSettingsSheet` only knows the calendar's `is_default` and `memberCount`. To know the user's role on this calendar, the sheet caller (CalendarSwitcherSheet) needs to pass `userRole`. Calendar model already exposes `userRole` from the backend response, so that's wired by the foundation epic.
- Invite-link UX simpler than recipe-book: only one role ('editor'), so no role selector on the link tab. The note text says "Anyone with this link can join as editor."
- No deactivate-link functionality in this story — out of scope; deferred (mentioned in cal-share-4 as "if user wants out").

## Tasks / Subtasks

- [x] **Task 1 — `CalendarService.listCalendarMembers`** (AC: 5)
  - [x] Add `listCalendarMembers(String calendarId)` to `CalendarService`.
  - [x] Add corresponding `ApiClient.listCalendarMembers(String calendarId)` returning the raw response.
  - [x] Define `CalendarMember` model class with `userId`, `name`, `email`, `role`, `status`, `invitedById`, `createdAt`, `invitationId`.

- [x] **Task 2 — `ShareCalendarSheet` widget** (AC: 2, 3, 4)
  - [x] Create `app/lib/features/calendar/widgets/share_calendar_sheet.dart`.
  - [x] Tabs: Invite by email/username + Share link.
  - [x] Wire to `sendInvitation` + `createInviteLink` + clipboard / native share.
  - [x] Map known error codes to user-friendly messages.

- [x] **Task 3 — Wire into `CalendarSettingsSheet`** (AC: 1, 6, 7)
  - [x] Replace placeholder Members section. Render real list (current user + others + pending).
  - [x] Owner sees Share Calendar button → opens `ShareCalendarSheet`.
  - [x] Editor sees read-only list (no Share button, no per-row actions — those land in cal-share-4).
  - [x] Pull-to-refresh on the members list.
  - [x] Settings sheet caller passes `userRole`.

- [x] **Task 4 — Tests** (AC: 8)
  - [x] Widget tests for share sheet + settings sheet members section.

- [x] **Task 5 — Local CI**
  - [x] `cd app && flutter analyze lib/features/calendar/`
  - [x] `cd app && flutter test test/features/calendar/`

### Key Files
- Modify: `app/lib/features/calendar/services/calendar_service.dart`
- Modify: `app/lib/core/services/api_client.dart`
- Modify: `app/lib/features/calendar/models/calendar.dart` (add CalendarMember model — or new models/calendar_member.dart)
- Create: `app/lib/features/calendar/widgets/share_calendar_sheet.dart`
- Modify: `app/lib/features/calendar/widgets/calendar_settings_sheet.dart`
- Create: `app/test/features/calendar/share_calendar_sheet_test.dart`
