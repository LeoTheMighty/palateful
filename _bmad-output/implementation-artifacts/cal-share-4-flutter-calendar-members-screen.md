# Story cal-share-4: Flutter Calendar Members screen + promote/remove/leave UX

Status: ready-for-dev

## Story

As Leo,
I want a dedicated Members screen reachable from Calendar Settings (and later Profile)
that lists everyone on the calendar with their role,
so I can promote my partner to owner, remove someone I added by mistake,
or leave a calendar I don't want anymore.

## Acceptance Criteria

1. New screen `CalendarMembersScreen` at route `/calendar/:id/members?role=<owner|editor>`. Reachable from `CalendarSettingsSheet` (a "Manage members" trailing affordance on the Members section header).
2. Body sections: (a) **Members** — every active member with name, role chip, per-row menu (owner only); (b) **Pending Invitations** — every pending invitation with email/name + Cancel (owner only).
3. Per-row menu (owners only, on non-self active members):
   - **Promote to Owner** (if target is editor) → confirmation prompt: "Make [name] owner? **You'll become an editor** and can't invite or remove members after this." On confirm: PATCH /calendars/:id/members/:user_id with `{role: 'owner'}` → snackbar + reload + pop screen (caller is no longer owner).
   - **Remove from calendar** → confirmation prompt: "Remove [name]? They'll lose access." On confirm: DELETE /calendars/:id/members/:user_id → snackbar + reload.
4. Self row: caller sees a different action — **Leave calendar** (visible only when caller is editor; replaced with helper text "Transfer ownership first to leave." for owners). On tap: confirmation sheet "Leave '[calendar name]'? You'll lose access to the meals on this calendar. You can be re-invited later." On confirm: POST /calendars/:id/leave → pop two screens (members → settings was already dismissed; pop to calendar tab) + snackbar + invalidate calendarsListProvider + active calendar fallback.
5. Pending row: Cancel button (owner only) → DELETE /invitations/:invitation_id → snackbar + reload.
6. **Stale-state handling**: any 403 from the role-change endpoint shows snackbar "You're no longer the owner. Refresh." + force-reload. Any 409 (CALENDAR_OWNER_TRANSFER_CONFLICT) shows "Another owner change happened. Refresh." + reload.
7. Pull-to-refresh reloads the members list.
8. Widget tests for CalendarMember model + member-list rendering + promote-confirmation-copy + leave-flow basic structure.

## Implementation Notes

- Reuse `CalendarService.listCalendarMembers` and the new wrappers from cal-share-3.
- Cancel-invitation reuses existing `ApiClient.revokeInvitation(invitationId)`.
- Role chip styling matches the recipe-book members screen.
- Editor-leaves needs the right active-calendar fallback. Pattern matches `CalendarSettingsSheet._confirmDelete`: clear active id if it was the leaving calendar; invalidate `calendarsListProvider`.

## Tasks / Subtasks

- [x] **Task 1 — Members screen** (AC: 1–6)
  - [x] Create `app/lib/features/calendar/calendar_members_screen.dart`.
  - [x] Stateful, loads members on init + on reload.
  - [x] Renders Members + Pending sections.
  - [x] Owner-gated menu (Promote, Remove); self-row Leave (editor-only).

- [x] **Task 2 — Confirmation dialogs** (AC: 3, 4)
  - [x] Promote dialog with explicit downgrade copy.
  - [x] Remove dialog.
  - [x] Leave dialog naming the calendar by name.

- [x] **Task 3 — Wire route** (AC: 1)
  - [x] Add `/calendar/:id/members?role=<owner|editor>&name=<calendar-name>` GoRoute to `app_router.dart`.

- [x] **Task 4 — Wire from settings sheet** (AC: 1)
  - [x] Add a trailing chevron on the Members section header in `CalendarSettingsSheet` → pushes the new route on tap, dismissing the sheet.

- [x] **Task 5 — Local CI**
  - [x] `flutter analyze lib/features/calendar/`
  - [x] `flutter test test/features/calendar/`

### Key Files
- Create: `app/lib/features/calendar/calendar_members_screen.dart`
- Modify: `app/lib/core/router/app_router.dart`
- Modify: `app/lib/features/calendar/widgets/calendar_settings_sheet.dart`
- Create: `app/test/features/calendar/calendar_members_screen_test.dart`
