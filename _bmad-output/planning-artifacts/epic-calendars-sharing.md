<!-- refined via party-mode 2026-04-17 -->
# Epic: Calendars — Sharing (invite editors, member management, profile surface)

## Overview

The foundation epic (`epic-calendars-foundation`) lands calendars as first-class containers that every user owns one or more of, with a switcher, create/rename/delete, and a move-between-calendars action. But every calendar is still owner-only: no one else can even see it, let alone add or edit meals on it.

This epic closes the user's original ask — **share calendars with others and have them able to have full edit/add permissions too** — by extending the existing invitation system (see `docs/INVITATION_SYSTEM.md`) with a new `calendar` resource_type, wiring up direct invites + invite-link flows, and shipping a Calendar Members management screen plus a Profile "Shared Calendars" surface.

All new behavior builds on top of plumbing that already exists: `invitations` table, `invite_links` table, direct/email/username invite paths, deferred deep-link claiming, `INVITATION_RECEIVED` push notifications, and activity-log entries. Nothing new at the primitive layer — this is pattern application.

**Goal:** When this epic ships, Leo can tap Share on any calendar he owns, invite his fiancee by email or generate a shareable invite link, and the moment she accepts the calendar appears in her switcher under "Shared with Me" with full create/edit/delete rights on every meal and rule inside. He can promote her to owner or remove her later. She can leave whenever.

## End-User Flow

1. Leo opens the Calendar tab → taps the "Meal Prep ▾" header → taps the chevron next to Meal Prep → Calendar Settings sheet opens.
2. Where the foundation epic's Members section said "Sharing coming soon," a real section now appears: a list of members (currently just him with role "Owner") and a primary action **Share Calendar**.
3. He taps **Share Calendar** → a sheet offers two options, matching recipe-book sharing:
   - **Invite by email / username**: text field, role selector (locked to "Editor"), send.
   - **Share link**: creates an invite link (deep link `palateful://invite/<token>`), copies it to clipboard, shows it below with a "Copy" button and small text "Anyone with this link can join as an editor."
4. He picks email, types his fiancee's email, taps Send. Snackbar: "Invitation sent." The members list now shows a pending invite row: "jane@example.com · Pending · Editor · Cancel".
5. Jane (on her device) gets a push notification: "Leo invited you to 'Meal Prep'." Tapping the push deep-links her to her in-app invitation inbox (existing `InvitationsScreen`). She taps Accept → `activeCalendarProvider.setActive(newCalendarId)` fires → the calendar appears in her switcher under "Shared with Me" with name "Meal Prep" and a subtitle "Shared by Leo · 2 members" **and becomes her active calendar**. Snackbar: "You joined Meal Prep."
6. She taps it → grid renders Meal Prep's meals. She taps the FAB → plan-meal sheet defaults to Meal Prep. She adds Tuesday dinner. Leo opens his device → he sees Tuesday dinner on Meal Prep (after a refresh or on next load).
7. Leo taps the chevron next to Meal Prep in his switcher → Calendar Settings → Members now shows both of them. He taps Jane → a sheet offers "Promote to Owner" or "Remove from calendar." He promotes her; her role becomes "Owner", his becomes "Editor" (ownership transfer in one shot). He now has Editor rights; Jane has the management controls.
8. From Jane's side, she can now go to Calendar Settings → see Leo in the members list → the same promote/remove actions are available.
9. If Leo later wants out: from the settings sheet, there's a **Leave calendar** row (visible only for non-sole-owner memberships — Leo is Editor now, so he can leave). Tapping it opens a confirmation sheet: "Leave 'Meal Prep'? You'll lose access to [N] meals you can currently edit. Jane will remain the owner. You can be re-invited later." Confirm → his `calendar_users` row is archived → switcher falls back to his **default** calendar (per foundation fallback rule — not a silent vanish) → Jane sees an activity-log entry "Leo left Meal Prep" (no push — lower-stakes event).
10. From Leo's Profile tab, a new **Shared Calendars** row shows every calendar he's an editor on (but doesn't own). Tapping opens a list of those calendars; tapping one opens its members screen (the same one reachable from Calendar Settings). This is the low-prominence surface for "what am I an editor on?"

**What does not change:** the calendar grid rendering, the plan-meal sheet layout (except that the Calendar picker now includes calendars he's editor on, not just owner), meal-event-level `host/cohost/guest` participants (still work for per-meal RSVP + display; just no longer grant edit rights — that was established in foundation cal-found-2).

## Frontend Changes

Touches `app/lib/features/calendar/` (member management), `app/lib/features/invitations/` (small additions), `app/lib/features/profile/` (new surface), and reuses existing member-avatar + role-badge primitives.

- **`widgets/calendar_settings_sheet.dart`** (modify): replace the foundation-epic placeholder "Members — Sharing coming soon" section with the real member list + Share action. Matches the recipe-book settings visual language.
- **`widgets/share_calendar_sheet.dart`** (new): the Share sheet — email/username form + invite-link tab. Reuses the direct-invite input + invite-link pattern from recipe-book sharing.
- **`widgets/calendar_members_list.dart`** (new): renders current members + pending invitations with role, status, and per-row action menu (promote/demote/remove).
- **`features/calendar/calendar_members_screen.dart`** (new): full screen for member management. Reached from Calendar Settings (`chevron`) AND from Profile → Shared Calendars. Route: `/calendar/:id/members`.
- **`features/profile/shared_calendars_screen.dart`** (new): profile surface listing calendars the user is an editor on. Simple list; tapping a row deep-links to `/calendar/:id/members`.
- **`features/profile/profile_screen.dart`** (modify): activate the "Shared Calendars" row that the foundation epic scaffolded. Show a count badge ("3 shared") if relevant.
- **`features/invitations/invitations_screen.dart`** (modify): today this screen shows pending invitations for shared books / shopping lists / meal events. Add `calendar` resource_type rendering — a card showing calendar name, inviter display name, and Accept / Decline buttons. Reuses existing `InvitationCard` component (if the render path supports a new resource_type branch).
- **`services/calendar_service.dart`** (modify): add `listCalendarMembers(id)`, `updateCalendarMember(calendarId, userId, {role})`, `removeCalendarMember(calendarId, userId)`, `leaveCalendar(id)` — thin wrappers over the new backend endpoints.
- **`services/invitation_service.dart`** (modify): accept `calendar` as a valid resource_type; no-op for the client — existing send/accept/decline paths already parameterize by resource_type.
- **Router** (`core/router/app_router.dart`): add `/calendar/:id/members` route.
- **Tests**: widget tests for share sheet, members list, settings-sheet-with-real-members, promote-to-owner, remove-member, leave-calendar confirm, shared-calendars-profile-row, invitations-screen-renders-calendar-invite.

## Backend Changes

Extends the existing invitation system + adds calendar member-management endpoints.

- **`services/api/src/api/v1/invitations/helpers.py`** (modify): add `"calendar": {"editor"}` to `VALID_ROLES`. Add a conditional branch to `check_resource_permission()` that queries `calendars` + `calendar_users` — owner-role is required to invite; editor-role is NOT. Add a conditional branch to `create_membership()` that inserts into `calendar_users` with `role='editor'`, preserving `invited_by_id`. Add a lookup in `get_resource_name()` for `resource_type='calendar'` — returns `calendars.name`.
- **`services/api/src/api/v1/invitations/*.py`** (modify, light): no logic changes — the existing `POST /invitations` + accept/decline routes already parameterize resource_type. Validation just picks up the new allowed value via `VALID_ROLES`.
- **`services/api/src/api/v1/invite_link/*.py`** (modify, light): same — `resource_type='calendar'` is now a valid value. Link preview returns calendar name + `member_count` + owner display name.
- **`services/api/src/api/v1/calendar/list_calendar_members.py`** (new): returns all members of a calendar (active `calendar_users` rows + pending invitations targeting the calendar). Any calendar member can call; non-members 404.
- **`services/api/src/api/v1/calendar/update_calendar_member.py`** (new): PATCH the role on a `calendar_users` row. Owner-only. Supports promote-to-owner; in that path, atomically demotes the calling owner to editor in the same transaction ("transfer ownership" semantics).
- **`services/api/src/api/v1/calendar/remove_calendar_member.py`** (new): DELETE a member. Owner-only. If the owner tries to remove themselves without transferring ownership, returns `CALENDAR_OWNER_CANNOT_REMOVE_SELF` (new error code in the 26x range).
- **`services/api/src/api/v1/calendar/leave_calendar.py`** (new): DELETE the calling user's `calendar_users` row (archive). Self-only. Owners cannot leave — they must transfer ownership first (or delete the calendar). Returns 409 with `CALENDAR_OWNER_CANNOT_LEAVE`.
- **`services/api/src/routers/v1/calendar_router.py`** (modify): register the four new member endpoints.
- **Activity-log entries**: on invite-sent, invite-accepted, invite-declined, member-removed, owner-transferred, member-left — write `Activity` rows matching the invitation system's existing patterns. No new notification categories.
- **Tests**:
  - `test_invitation_calendar_resource.py`: send direct invite → accept → membership created; send email invite (no account) → signup → claim → pending in inbox → accept; invite-link create → join → membership created.
  - `test_calendar_member_management.py`: list members (self + peer); promote-to-owner transfers atomically; remove-member requires owner; owner-cannot-remove-self; leave-calendar as editor works, as owner returns 409.
  - Regression: editor role gets full create/update/delete rights on meal_events and recurrence rules in the calendar (verified via the foundation cal-found-2 tests, re-run with editor-role user).

## Infrastructure Changes

- **Migration**: none. All tables were created in the foundation epic. This epic is code-only on the backend.
- **Worker scheduling**: no change.
- **Env vars / secrets**: none.
- **Terraform / AWS**: none.
- **CI**: existing matrix covers. No new test runners.
- **Firebase push**: the existing `INVITATION_RECEIVED` push notification dispatcher already handles arbitrary resource_types via the invitation-system helpers. No new notification category, no new FCM config.

## Design Principles (refined via party-mode 2026-04-17)

1. **Reuse the invitation system; one resource_type branch in three functions is the whole backend** (backend). A new `resource_type='calendar'` branch in `VALID_ROLES`, `check_resource_permission`, `create_membership` + a lookup in `get_resource_name`, plus four member-management endpoints — total surface area. No new tables, no new push types, no new invite claim flow.
2. **Owner + editor only. No viewer, ever** (PM). Inherited lock from foundation. Don't sneak viewer back in as a "read-only" mode.
3. **Promote-to-owner confirmation must name the caller's loss of power explicitly** (UX). Copy: "Make [name] owner? **You'll become an editor** and can't invite or remove members after this." The caller's own downgrade is the core fact — don't bury it.
4. **Ownership transfer is atomic and serialized per-calendar** (backend). Promote + demote in one transaction, guarded by `SELECT ... FOR UPDATE` on both the current-owner row and the target-member row to prevent simultaneous-cross-transfer races. Partial unique index `(calendar_id) WHERE role='owner' AND archived_at IS NULL` enforces "exactly one owner" at DB level. Never two owners; never zero.
5. **Owners cannot leave via any path** (backend). Both remove-self-as-owner and leave-while-owner return 409 with the *same* error code `CALENDAR_OWNER_CANNOT_LEAVE`. One code for "owner tries to exit." The draft's two separate codes were redundant.
6. **Leaving is a real flow with a goodbye moment, not a silent archive** (UX). Confirmation sheet names the blast radius (N meals lost access to) + promises re-invite as recovery. Archive the `calendar_users` row, fall back to the user's default calendar per the foundation fallback rule, and write both an `Activity` entry (user-visible) and an audit-log row (`service="audit"`, ops-visible) distinguishing leave from remove.
7. **Meal-event-level participants are NOT cleaned up on calendar-member removal** (backend). Removing Jane from a calendar does NOT delete her `meal_event_participants` rows on events in that calendar. Participants are an orthogonal primitive — they drive per-meal RSVP + display, not edit authority. Post-foundation, they give no edit rights; they just stay as display-only metadata.
8. **Invite-link previews respect privacy** (PM). `GET /v1/invite-links/{token}` returns calendar name + member count + owner display name + role (`editor`, so the invitee knows they're joining as full-edit before accepting). No meal content. No member emails.
9. **Members list is eventually-consistent, not realtime** (frontend + UX). Pull-to-refresh + reload-on-focus is the contract. Two owners editing the same member's role simultaneously rely on backend serialization (principle #4) + a graceful 403 path with a "refresh" hint on the losing device. No AppSync subscriptions for this epic.
10. **Audit-log every member mutation with `service="audit"`** (backend). Inherited lock. Invite sent, invite accepted, invite declined, member removed, ownership transferred, member left — all six go to `error_logs` with `service="audit"` alongside their user-visible `Activity` rows.
11. **`require_calendar_access` is the one auth primitive; no reinvention** (backend). Member-mutating endpoints pass `roles={'owner'}` to the dep; read-only endpoints pass `roles={'owner','editor'}`.
12. **Ownership transfer does NOT flip `is_default`** (backend). Inherited lock. The `is_default` flag is per-user (via `owner_id` on the calendar at creation time) and doesn't travel with ownership. Transfer changes `role` in `calendar_users`, nothing else.
13. **`CalendarPickerSheet` is the reusable picker primitive** (frontend). Inherited lock. This epic doesn't introduce a new picker — the Profile "Shared Calendars" surface is a static list, no picker needed.
14. **Shared Calendars on Profile is a low-prominence surface** (UX). One row, deep-links to the list, no badges or counts beyond "N shared." Users primarily manage sharing from Calendar Settings on the calendar itself. The Profile row is for "what am I an editor on?"
15. **No feature flags** (devops). Ships directly behind the foundation-epic migration. Rollback removes the new handlers + the `VALID_ROLES` entry; the data model is stable, untouched.

## File Structure (expected)

```
app/lib/features/calendar/
├── calendar_members_screen.dart            # NEW — full screen for member management
├── widgets/
│   ├── share_calendar_sheet.dart           # NEW — email/username + invite-link tabs
│   ├── calendar_members_list.dart          # NEW
│   └── calendar_settings_sheet.dart        # MODIFIED — real Members section
└── services/calendar_service.dart          # MODIFIED — member endpoints

app/lib/features/profile/
├── shared_calendars_screen.dart            # NEW — profile surface list
└── profile_screen.dart                     # MODIFIED — Shared Calendars row active

app/lib/features/invitations/
└── invitations_screen.dart                 # MODIFIED — render calendar invites

app/lib/core/router/app_router.dart         # MODIFIED — add /calendar/:id/members route

services/api/src/
├── api/v1/invitations/helpers.py           # MODIFIED — calendar resource_type branches
├── api/v1/calendar/
│   ├── list_calendar_members.py            # NEW
│   ├── update_calendar_member.py           # NEW (handles promote + demote + transfer)
│   ├── remove_calendar_member.py           # NEW
│   └── leave_calendar.py                   # NEW
└── routers/v1/calendar_router.py           # MODIFIED — register the four endpoints

services/api/tests/
├── test_invitation_calendar_resource.py    # NEW
└── test_calendar_member_management.py      # NEW
```

## Story Map

| # | Story | Priority | Est. Effort | Depends on |
|---|-------|----------|-------------|------------|
| cal-share-1 | Invitation + invite-link extension for `resource_type=calendar` (BE) | P0 | 0.5 d | `epic-calendars-foundation` |
| cal-share-2 | Calendar member-management endpoints: list / update role (promote) / remove / leave (BE) | P0 | 1 d | cal-share-1 |
| cal-share-3 | Flutter Share Calendar sheet (email/username + invite-link) + wired into Calendar Settings | P0 | 1 d | cal-share-1 |
| cal-share-4 | Flutter Calendar Members screen + settings-sheet Members section (real) + promote/remove/leave UX | P0 | 1 d | cal-share-2 |
| cal-share-5 | Profile "Shared Calendars" surface + invitations-screen calendar-invite card + activity-log entries wired through | P1 | 0.5 d | cal-share-3, cal-share-4 |

**Total estimated effort: 4 days.**

**Sequencing:** cal-share-1 → cal-share-2 ∥ cal-share-3 → cal-share-4 → cal-share-5.

---

## Story cal-share-1: Invitation & invite-link extension for calendar resource_type

As the backend, I want to accept `resource_type='calendar'` on every invitation and invite-link path so that any Flutter-side sharing UI can just call the existing endpoints with a new value and get full behavior (direct invite, email-no-account, invite-link, accept, decline, claim, revoke).

### Acceptance Criteria

1. `VALID_ROLES` in `services/api/src/api/v1/invitations/helpers.py` gains `"calendar": {"editor"}`.
2. `check_resource_permission()` gains a `calendar` branch: (a) loads the calendar by id; (b) 404 if archived or not found; (c) requires the caller to be owner on `calendar_users` (non-owner members cannot invite — consistent with recipe-book behavior).
3. `create_membership()` gains a `calendar` branch: inserts `calendar_users (calendar_id, user_id, role='editor', invited_by_id)`. If the user is already an active member: idempotent success (returns 200 with existing membership). If the user has an archived membership: un-archives and updates role.
4. `get_resource_name()` gains a `calendar` branch: returns `calendars.name`.
5. `POST /v1/invitations` with `resource_type='calendar'`, `role='editor'`, and a valid `to_user_id` / `to_username` / `to_email` creates an `Invitation` row and (for user targets) dispatches the existing `INVITATION_RECEIVED` push.
6. `POST /v1/invitations/{id}/accept` on a calendar invitation creates the `calendar_users` row, writes an `Activity` row of kind `joined` with `resource_type='calendar'`, and dispatches the existing `INVITATION_ACCEPTED` push to the inviter.
7. `POST /v1/invite-links` with `resource_type='calendar'` creates a link token. `GET /v1/invite-links/{token}` returns `{resource_type: 'calendar', resource_name, owner_display_name, member_count, state}` — no meal content, no member emails. `POST /v1/invite-links/{token}/join` adds the joiner as editor.
8. `POST /v1/invitations/claim` (signup flow) correctly matches pending `to_email` invitations for `resource_type='calendar'` and surfaces them in the user's pending inbox — matches the existing claim semantics.
9. Regression test: invitation rate-limit (30/24h per user) still applies across resource_types; mixing 15 recipe-book + 15 calendar invites in 24h hits the limit.
10. **Archived-membership reactivation**: `create_membership()` detects an existing archived `calendar_users` row for the invitee and un-archives it (sets `archived_at=NULL`, updates `role='editor'`, updates `invited_by_id` to the new inviter). `check_resource_permission` treats archived rows as non-membership — so re-invite works rather than 409'ing with `INVITATION_ALREADY_MEMBER`. Tested explicitly.
11. **Push-payload completeness audit**: verify the existing `INVITATION_RECEIVED` FCM payload includes `resource_name` so the lock-screen renders "Leo invited you to 'Meal Prep'" without an app-load round-trip. If missing, add it in this story (it's a trivial payload addition; scope creep is fine since it's the same FCM dispatcher). Document payload shape in the test.
12. Tests in `test_invitation_calendar_resource.py` cover: send-by-user-id, send-by-email-no-account → signup → claim, send-by-username, invite-link-full-flow, send-as-editor-forbidden (non-owner invite attempt → 403), send-duplicate-invite (second send to same user for same calendar → `INVITATION_ALREADY_SENT` 242), self-invite (owner invites themselves → `INVITATION_SELF_INVITE` 247), **re-invite-of-previously-removed-member-reactivates-archived-row**, and **push-payload-includes-resource-name**.

### Key Files
- Modify: `services/api/src/api/v1/invitations/helpers.py`
- Modify: `services/api/src/api/v1/invite_link/get_invite_link.py`, `join_invite_link.py` (resource-type branches if needed)
- Create: `services/api/tests/test_invitation_calendar_resource.py`

---

## Story cal-share-2: Calendar member management endpoints

As an owner of a calendar, I want to list members, promote someone, remove them, or leave the calendar (as an editor) so that I can actually manage who has access long-term.

### Acceptance Criteria

1. `GET /api/v1/calendars/{id}/members` returns all active `calendar_users` rows for the calendar PLUS all pending `Invitation` rows targeting the calendar (merged shape: `{user_id, display_name, email, role, status: 'active' | 'pending' | 'archived', invited_by_id, created_at}`). Any calendar member can call; non-members 404. Uses `require_calendar_access` with `roles={'owner','editor'}`.
2. `PATCH /api/v1/calendars/{id}/members/{user_id}` accepts `{role}`. Owner-only via `require_calendar_access` with `roles={'owner'}`. Supported transitions: `editor` ↔ `owner`. **Atomicity**: the handler opens a transaction, issues `SELECT ... FOR UPDATE` on both the current-owner's `calendar_users` row AND the target-member's row, then executes promote + demote in that transaction. Two concurrent PATCH requests transferring ownership to different targets → the second serializes behind the first and either succeeds against already-demoted state (no-op) or returns `CALENDAR_OWNER_TRANSFER_CONFLICT` (409). Never: two owners, zero owners. Ownership transfer does NOT flip `is_default` on the calendar (principle #12). Activity-log entry of kind `ownership_transferred` + audit-log row.
3. `DELETE /api/v1/calendars/{id}/members/{user_id}` archives the member's `calendar_users` row. Owner-only. If `user_id == caller.id` AND caller is owner, returns **`CALENDAR_OWNER_CANNOT_LEAVE`** with 409 (same code as leave-while-owner — principle #5). Member's `meal_event_participants` rows on events in this calendar are NOT cleaned up — they persist (display-only, no edit authority post-foundation; principle #7). Member's `last_opened_at` and `invited_by_id` are preserved on the archived row for future reactivation. Activity-log entry of kind `removed` + audit-log row.
4. `POST /api/v1/calendars/{id}/leave` archives the caller's own `calendar_users` row. If caller is the owner, returns `CALENDAR_OWNER_CANNOT_LEAVE` with 409. No check against `meal_event_participants` — the participant rows are orthogonal. Activity-log entry of kind `left` + audit-log row.
5. Re-join: if a previously-archived member is re-invited + accepts, the existing `calendar_users` row is un-archived and `role` is updated to the new role (consistent with `shopping_list_users` reactivation pattern + cal-share-1 AC #10).
6. **Shared-calendar shopping-list integration regression**: Jane (editor on Leo's shared Meal Prep calendar) calls `populate_from_calendar_range` on her shopping list → meals from Leo's Meal Prep calendar appear in her list. Test confirms the foundation cal-found-2 union-across-calendars logic works for multi-user scenarios, not just multi-own-calendar scenarios.
7. Tests in `test_calendar_member_management.py`: list-members-inclusive (active + pending + self), promote-atomic-transfer, promote-concurrent-cross-transfer-conflict (`SELECT ... FOR UPDATE` serializes), promote-is-default-preserved-on-calendar, promote-as-editor-403, remove-happy-path, remove-does-not-cascade-meal-event-participants, owner-cannot-remove-self-409 (`CALENDAR_OWNER_CANNOT_LEAVE`), owner-cannot-leave-409, editor-leave-happy-path, rejoin-reactivates-archived-row, shared-calendar-shopping-list-populate-includes-other-members-meals, non-member-calls-403.

### Key Files
- Create: `services/api/src/api/v1/calendar/list_calendar_members.py`, `update_calendar_member.py`, `remove_calendar_member.py`, `leave_calendar.py`
- Modify: `services/api/src/routers/v1/calendar_router.py`
- Create: `services/api/tests/test_calendar_member_management.py`

---

## Story cal-share-3: Flutter Share Calendar sheet + Calendar Settings wire-up

As Leo, I want a Share action on the calendar I own that lets me invite someone by email/username or copy an invite link so that sharing is the same two-tap flow I already know from recipe books.

### Acceptance Criteria

1. `CalendarSettingsSheet` (from the foundation epic) replaces its "Sharing coming soon" placeholder with a real Members section that: shows the calling user's own row first, followed by other active members + pending invitations. For owners, a primary action button at the bottom reads **Share Calendar**. For editors, the Members section is read-only (no Share button, no per-row actions).
2. Tapping **Share Calendar** opens `ShareCalendarSheet` — a bottom sheet with two tabs/segments: **Invite by email** (default) and **Share link**.
3. The Invite by email tab shows: an email/username text field, a non-interactive role indicator ("Editor"), and a Send button. On Send: calls `POST /v1/invitations` with `resource_type='calendar'`, `role='editor'`, the calendar id, and the entered target. Success → snackbar "Invitation sent to [target]"; members list refreshes to include the pending row. Failure → inline error with code-to-message mapping (already-member → "[target] is already a member", already-sent → "You already invited [target]", self-invite → "You can't invite yourself").
4. The Share link tab shows: if a link exists for this calendar, show it with Copy + Deactivate buttons; else show a Create link button. On create: calls `POST /v1/invite-links` with `resource_type='calendar'`, returns the token, constructs `palateful://invite/{token}`, copies to clipboard, and displays it with the same Copy/Deactivate affordances.
5. All members (owner + editors) can open the Share sheet in read-only preview mode; only owners can actually Send / Create link (buttons disabled for editors with helper "Only the owner can invite new members" — consistent with recipe-book behavior).
6. **Self-invite guard on the Invite-by-email tab**: show the caller's own email/username in a disabled "You" row at the top of the input suggestion list. Prevents the typo-leading-to-self-invite `INVITATION_SELF_INVITE` (247) error — catches it at UI before the roundtrip.
7. Member-count in the switcher sheet updates reactively as invitations are accepted (refresh on sheet open is fine; real-time is not required for this epic — principle #9).
8. **Pull-to-refresh** on the Calendar Settings sheet members section — Leo and Jane both viewing simultaneously rely on this + the 403-with-refresh-hint path (cal-share-4) for stale state.
9. Widget tests: share-sheet renders, send invite happy path, send invite duplicate error, self-invite-prevented-at-UI, create-link, copy-link (mocked clipboard), editor-sees-read-only, owner-sees-full, pull-to-refresh-reloads-members.

### Key Files
- Create: `app/lib/features/calendar/widgets/share_calendar_sheet.dart`
- Modify: `app/lib/features/calendar/widgets/calendar_settings_sheet.dart` (Members section + Share button)
- Modify: `app/lib/features/calendar/services/calendar_service.dart` (invitation + invite-link wrappers, or reuse existing `InvitationService` with `resource_type='calendar'`)
- Tests: `app/test/features/calendar/share_calendar_sheet_test.dart`

---

## Story cal-share-4: Flutter Calendar Members screen + promote / remove / leave UX

As Leo, I want a dedicated Members screen I can reach both from Calendar Settings and from Profile that lists everyone on the calendar with their role so I can promote my partner to owner, remove someone I mistakenly added, or leave a calendar I no longer want access to.

### Acceptance Criteria

1. New screen `CalendarMembersScreen` at route `/calendar/:id/members`. Accessible from (a) Calendar Settings sheet → trailing chevron on the Members section header, (b) Profile → Shared Calendars row → tap a calendar (wired in cal-share-5).
2. Screen body: top section "Members" with rows for every active member (display name, email optional, role chip, per-row menu). Second section "Pending Invitations" with rows for unresolved invitations (email/display name, role chip, Cancel button for owner).
3. Per-row menu on active members, owner only: **Promote to Owner** (if target is editor; confirmation prompt "Make [name] owner? **You'll become an editor** and can't invite or remove members after this.") and **Remove from calendar** (confirmation prompt "Remove [name]? They'll lose access to this calendar."). Self-row: Leave calendar (editor only — hidden for the owner, replaced with a helper text "Transfer ownership first to leave.").
4. Promote → `PATCH /calendars/{id}/members/{user_id}` with `{role: 'owner'}` → on success, snackbar "[name] is now the owner" + screen reloads to show the demoted caller.
5. Remove → `DELETE /calendars/{id}/members/{user_id}` → snackbar "[name] removed" + screen reloads.
6. Leave (editor) → confirmation sheet: "Leave '[calendar name]'? You'll lose access to **[N] meals** you can currently edit. You can be re-invited later." [N] computed on the client from the last-loaded meal count for the calendar; if unknown, fall back to "You'll lose access to the meals on this calendar." Confirm → `POST /calendars/{id}/leave` → snackbar "You left [calendar name]" + `activeCalendarProvider` falls back to the user's default calendar + navigator pops to the Calendar tab + switcher reloads (the calendar is gone from Shared with Me).
7. Pending invitation row: Cancel button (owner only) → `DELETE /invitations/{id}` → snackbar "Invitation canceled" + row disappears.
8. **Stale-state handling (no realtime)**: if the screen was loaded when Leo was owner, and Jane (elsewhere) promoted herself to owner, Leo's next action returns 403 from backend. Client catches 403 → snackbar "You're no longer the owner. Refresh." + force-refresh the screen. Members list is eventually-consistent (principle #9); pull-to-refresh available.
9. Activity-log surface: NOT in this epic. The activity entries exist in the DB (cal-share-2 AC #2/3/4) but there's no in-app feed. If the user asks for one later, it's a separate screen.
10. Widget tests: members-list renders with self + others + pending, promote-flow-explicit-downgrade-copy, remove-flow, leave-flow-as-editor-names-meal-count, leave-hidden-for-owner, cancel-invitation-flow, editor-role-no-management-menu, stale-owner-403-forces-refresh.

### Key Files
- Create: `app/lib/features/calendar/calendar_members_screen.dart`, `widgets/calendar_members_list.dart`
- Modify: `app/lib/features/calendar/services/calendar_service.dart`
- Modify: `app/lib/core/router/app_router.dart` (register `/calendar/:id/members`)
- Tests: `app/test/features/calendar/calendar_members_screen_test.dart`

---

## Story cal-share-5: Profile "Shared Calendars" row, invitations-screen calendar-invite card, polish

As Leo, I want a low-prominence surface in Profile that lists the calendars I'm an editor on (but don't own) and a clear invitation card for calendar invites in my inbox so that all the "where do I manage shared stuff?" surfaces have complete coverage.

### Acceptance Criteria

1. Profile screen's "Shared Calendars" row (scaffolded in foundation cal-found-3, hidden/disabled) becomes visible and active. Row shows a count badge when the user has >0 shared-as-editor calendars.
2. Tap opens `SharedCalendarsScreen` — a simple list of editor-role calendars (name, owner display name subtitle, member-count trailing). Empty state copy: "No shared calendars yet. When someone invites you to their calendar, it'll show up here." Tap a row → navigates to `/calendar/:id/members` (the screen from cal-share-4).
3. **`InvitationCard` polymorphism audit + refactor**: inspect the current `InvitationCard` component (in `app/lib/features/invitations/`). If it's hard-coded for recipe-book/shopping-list/meal-event resource types (likely), refactor to dispatch on `resource_type` via a mapping table: `{resource_type → (headline_template, subtitle, icon)}`. This refactor lives inside this story — small enough to justify, large enough to justify the explicit AC. After refactor, adding `calendar` is one row in the mapping.
4. `InvitationsScreen` adds rendering for `resource_type='calendar'` invitation cards: headline "[inviter name] invited you to join [calendar name]", subtitle "Editor access", Accept/Decline buttons. Uses the refactored `InvitationCard`.
5. On Accept: calls existing `POST /invitations/{id}/accept`, on success **explicitly calls `activeCalendarProvider.setActive(newCalendarId)`** (per foundation lock), refreshes the switcher (the new calendar appears under "Shared with Me"), navigates to the Calendar tab, snackbar "You joined [calendar name]."
6. On Decline: calls existing `POST /invitations/{id}/decline`, card disappears from inbox, no navigation.
7. Push notification landing: tapping the `INVITATION_RECEIVED` push for a calendar deep-links to the Invitations screen (existing behavior — confirm the calendar-invite card renders via the refactored component).
8. Widget tests: shared-calendars-list renders, shared-calendars-empty-state-copy, tap-navigates-to-members, invitations-screen-calendar-invite-renders-via-polymorphic-card, accept-flow-calls-setActive-and-navigates, decline-flow-removes-card, invitation-card-refactor-preserves-recipe-book-rendering (regression).

### Key Files
- Create: `app/lib/features/profile/shared_calendars_screen.dart`
- Modify: `app/lib/features/profile/profile_screen.dart` (activate Shared Calendars row)
- Modify: `app/lib/features/invitations/invitations_screen.dart` (calendar-invite branch)
- Modify: `app/lib/core/router/app_router.dart` (route for shared-calendars-screen)
- Tests: `app/test/features/profile/shared_calendars_screen_test.dart`, `app/test/features/invitations/invitations_screen_calendar_test.dart`

---

## Dependencies

- **Upstream**: `epic-calendars-foundation` (hard — assumes `calendars` + `calendar_users` tables, calendar CRUD endpoints, `CalendarSettingsSheet` scaffold, and the Profile row placeholder all exist).
- **Downstream**: none planned. Overlay / color-coded view, viewer role, and per-list calendar scoping on shopping lists are explicitly out of scope and deferred.
- **Cross-cutting**: the existing invitation system (`docs/INVITATION_SYSTEM.md`) is the substrate; this epic is a thin resource-type extension.

## Definition of Done (Epic Level)

- `resource_type='calendar'` is a valid value on every invitation and invite-link endpoint; direct-invite (user_id/username/email), email-claim-on-signup, and invite-link (create → preview → join) flows all work end-to-end.
- A user can own a calendar, invite someone as editor (via email or invite link), see them appear in the members list, promote them to owner (with atomic `SELECT ... FOR UPDATE`–serialized ownership transfer), remove them, or leave the calendar (as editor).
- The invitee receives the existing `INVITATION_RECEIVED` push with `resource_name` in the payload; accepting reveals the calendar in their switcher under "Shared with Me" via an explicit `activeCalendarProvider.setActive` call, and the inviter gets the existing `INVITATION_ACCEPTED` push.
- Editors get full create/edit/delete rights on meal_events and recurrence rules in the shared calendar — verified via regression over the foundation cal-found-2 authorization tests with editor-role users.
- Host/cohost/guest `meal_event_participants` continue to display correctly on shared meals but do NOT grant edit rights to non-members — same regression test, re-flagged in this epic's DoD.
- Shared-calendar shopping-list populate works end-to-end: Jane (editor on Leo's calendar) calls `populate_from_calendar_range` → Leo's meals appear in her list.
- Calendar Members screen is reachable from Calendar Settings and from Profile → Shared Calendars.
- `SharedCalendarsScreen` in Profile lists calendars the user is an editor on (not owner), with the empty-state copy.
- Every member mutation writes both a user-visible `Activity` row AND an ops-visible audit row (`error_logs` with `service="audit"`).
- **Deploy gate**: this epic does not deploy until the foundation migration's `error_logs service='migrator'` integrity-check entries confirm zero-NULL `calendar_id` rows across `meal_events` and `meal_recurrence_rules`. Infra check before first cal-share merge.
- All P0 tests pass in CI.

## Open Questions — Resolved 2026-04-17

All party-mode-surfaced questions locked by the user:

- ✅ **Max members per calendar**: no cap (party-mode lock — friends-and-family NFR18 scale).
- ✅ **In-app activity feed**: don't ship (party-mode lock — nothing users didn't ask for).
- ✅ **Invite-link expiry default**: **no expiry** for calendar invite links. User-revocable via the Deactivate button on the Share sheet.
- ✅ **Email-invite deliverability**: **no email for now**. Status quo per `INVITATION_SYSTEM.md`; inviter shares the link out-of-band. Revisit as an invitation-system-level upgrade if it becomes a pain point across resource types.
- ✅ **Rate-limit**: leave at 30/24h. Raise later if anyone hits it.
- ✅ **Re-invite of previously-removed member**: preserve the full push + accept flow (they get the invite in their inbox, not auto-rejoined). Archived row un-archives only on accept, not on invite send.
- ✅ **`INVITATION_RECEIVED` push-payload completeness**: audit + patch inside cal-share-1 (AC #11). Trivial payload addition; same FCM dispatcher.
