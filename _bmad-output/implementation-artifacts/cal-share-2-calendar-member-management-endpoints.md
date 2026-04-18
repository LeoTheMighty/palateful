# Story cal-share-2: Calendar member management endpoints

Status: ready-for-dev

## Story

As an owner of a calendar,
I want endpoints to list members, change a member's role (including transfer ownership), remove a member, and leave a calendar (as an editor),
so that calendars can actually be managed long-term, not just shared once.

## Acceptance Criteria

1. `GET /api/v1/calendars/{calendar_id}/members` returns active `calendar_users` rows + pending `Invitation` rows targeting this calendar. Shape per row: `{user_id, name, email, role, status: 'active'|'pending', invited_by_id, created_at}`. Any active member can call (owner OR editor — `roles={'owner','editor'}`); non-members → 404 `CALENDAR_NOT_FOUND` (existence-leak guard, matches `get_calendar`).
2. `PATCH /api/v1/calendars/{calendar_id}/members/{user_id}` accepts `{role}`. Owner-only. Supported transitions: `editor → owner` (transfer ownership; **caller is atomically demoted to editor in the same transaction**). `owner → editor` directly is blocked (caller is the only owner; demotion would leave the calendar ownerless) — return 400 `CALENDAR_OWNER_TRANSFER_REQUIRED` (270, new). 400 `CALENDAR_INVALID_ROLE` (271, new) for any other role string.
3. Ownership transfer atomicity: the handler issues `SELECT ... FOR UPDATE` on both the current-owner row AND the target-member row, then flips both roles in one transaction. The DB partial-unique-index (`uq_calendars_owner_is_default_active` is per-user; no per-calendar owner index exists today — add one in this story: `uq_calendar_users_one_owner_active` on `(calendar_id) WHERE role='owner' AND archived_at IS NULL`). Concurrent transfers serialize on the `FOR UPDATE` lock; one wins, the other sees the already-mutated state and either no-ops (target is already owner) or raises `CALENDAR_OWNER_TRANSFER_CONFLICT` (272, new).
4. Ownership transfer does NOT touch `Calendar.is_default`. The `is_default` flag is per-user (current owner → maybe the new owner has a different default — irrelevant; `is_default` is only meaningful to the calendar's owner, and the foundation epic stipulates is_default doesn't move).
5. `DELETE /api/v1/calendars/{calendar_id}/members/{user_id}` archives the row. Owner-only. If `user_id == caller.id` AND caller is owner → 409 `CALENDAR_OWNER_CANNOT_LEAVE` (273, new) — same code as leave-while-owner. Removed member's `meal_event_participants` rows are NOT cleaned up (orthogonal primitive, principle #7). Removed member's `last_opened_at` and `invited_by_id` preserved on the archived row for future reactivation.
6. `POST /api/v1/calendars/{calendar_id}/leave` archives the caller's own `calendar_users` row. If the caller is owner → 409 `CALENDAR_OWNER_CANNOT_LEAVE`. Same single error code regardless of via-remove vs. via-leave.
7. Re-join: a previously-archived `calendar_users` row gets un-archived + role updated when the user accepts a new invitation (consistent with cal-share-1 AC #10 — `create_membership` already handles this).
8. **Activity-log entries** — every mutation writes one `Activity` row matching the existing patterns:
   - Promote: `action='ownership_transferred'`, `resource_type='calendar'`, `resource_id=calendar_id`, `target_type='user'`, `target_id=new_owner_user_id`, `details={'previous_owner_id': caller.id, 'new_owner_id': target_id}`.
   - Remove: `action='removed'`, `resource_type='calendar'`, `target_type='user'`, `target_id=removed_user_id`, `details={'removed_by_id': caller.id}`.
   - Leave: `action='left'`, `resource_type='calendar'`, `target_type='user'`, `target_id=caller.id`.
9. **Audit log** — every mutation also writes an `ErrorLog` row with `service='audit'` (per `delete_calendar.py` pattern), so promote/remove/leave are queryable from ops without polluting `service='api'` dashboards.
10. Tests in `test_calendar_member_management.py` cover: list-members-active-and-pending-merged; list-members-non-member-404; promote-editor-to-owner-atomically-demotes-caller; promote-owner-to-editor-rejected-400; promote-as-editor-403; promote-target-not-a-member-404; remove-happy-path; remove-self-as-owner-409; remove-as-editor-403; remove-non-member-target-404; leave-as-editor-happy-path; leave-as-owner-409; leave-when-not-a-member-404; verify-activity-and-audit-rows-on-each-mutation.
11. Migration: add the partial unique index `uq_calendar_users_one_owner_active` on `calendar_users(calendar_id) WHERE role='owner' AND archived_at IS NULL`. Concurrent — `CREATE UNIQUE INDEX CONCURRENTLY ... IF NOT EXISTS`. Foundation epic created the table with no per-calendar owner constraint; this constraint is the DB-level guarantee behind AC #3.

## Implementation Notes

- All four new endpoints live in `services/api/src/api/v1/calendar/`. Register in `services/api/src/routers/v1/calendar_router.py`.
- Activity model uses `target_type` / `target_id` for the affected user — see `models/activity.py`.
- ErrorLog audit pattern: `service='audit'`, `error_type='CalendarMemberAudit'`, `error_message='<verb> <subject> by <actor>'`, `user_id=caller.id`. See `delete_calendar.py:144-153`.
- New error codes (`error_code.py` Calendar block 261–269 is full → use 270+ as Calendar-Sharing extension):
  - `CALENDAR_OWNER_TRANSFER_REQUIRED = 270`
  - `CALENDAR_INVALID_ROLE = 271`
  - `CALENDAR_OWNER_TRANSFER_CONFLICT = 272`
  - `CALENDAR_OWNER_CANNOT_LEAVE = 273`
- Note: 270 (PANTRY_NOT_FOUND) already exists. Renumber to 280–283 to avoid collision (Pantry block is 270-289).
- Story uses 280–283 for the four new codes. Confirm before implementing.

## Tasks / Subtasks

- [x] **Task 1 — Migration: partial unique index for "one active owner per calendar"** (AC: 11)
  - [x] Add Alembic migration creating `uq_calendar_users_one_owner_active` (`UNIQUE INDEX CONCURRENTLY ... ON calendar_users (calendar_id) WHERE role='owner' AND archived_at IS NULL`).
  - [x] Add the corresponding `Index(...)` to `CalendarUser.__table_args__` so `migrator:check-models` stays clean.
  - [x] Verify against the alembic baseline by running `npx nx run migrator:check-models`.

- [x] **Task 2 — Error codes** (AC: 2, 3, 5, 6)
  - [x] Add the four new codes (`CALENDAR_OWNER_TRANSFER_REQUIRED=280`, `CALENDAR_INVALID_ROLE=281`, `CALENDAR_OWNER_TRANSFER_CONFLICT=282`, `CALENDAR_OWNER_CANNOT_LEAVE=283`) to `error_code.py`.

- [x] **Task 3 — Endpoint: `ListCalendarMembers`** (AC: 1)
  - [x] Create `services/api/src/api/v1/calendar/list_calendar_members.py`. Read-only — accept owner OR editor.
  - [x] Membership precheck → 404 if not a member.
  - [x] Two queries: active `calendar_users` rows joined to `User`, plus pending `Invitation` rows for this `(resource_type='calendar', resource_id=calendar_id)`. Merge into a flat `members` list with a `status` discriminator.

- [x] **Task 4 — Endpoint: `UpdateCalendarMember`** (AC: 2, 3, 4, 8, 9)
  - [x] Create `services/api/src/api/v1/calendar/update_calendar_member.py`.
  - [x] Owner-only precheck. Role validation (only `owner` accepted as input — caller demote-to-editor flow only triggered via promote-target-to-owner path; direct demote rejected).
  - [x] Transaction: lock both rows with `with_for_update()`; flip target → owner; flip caller → editor; flush; commit handled by FastAPI middleware.
  - [x] Activity row + audit ErrorLog row.
  - [x] Catch IntegrityError on the partial unique index (concurrent transfer race), translate to 409 `CALENDAR_OWNER_TRANSFER_CONFLICT`.

- [x] **Task 5 — Endpoint: `RemoveCalendarMember`** (AC: 5, 7, 8, 9)
  - [x] Create `services/api/src/api/v1/calendar/remove_calendar_member.py`.
  - [x] Owner-only precheck. Self-as-owner removal → 409 `CALENDAR_OWNER_CANNOT_LEAVE`.
  - [x] Target row 404 if not active member. Set `archived_at = now`. Preserve `last_opened_at`, `invited_by_id`.
  - [x] Activity row + audit ErrorLog row.

- [x] **Task 6 — Endpoint: `LeaveCalendar`** (AC: 6, 8, 9)
  - [x] Create `services/api/src/api/v1/calendar/leave_calendar.py`.
  - [x] Caller's own row precheck. If caller is owner → 409 `CALENDAR_OWNER_CANNOT_LEAVE`. Else archive.
  - [x] Activity row + audit ErrorLog row.

- [x] **Task 7 — Router registration**
  - [x] Add the four endpoints to `services/api/src/api/v1/calendar/__init__.py` exports.
  - [x] Wire routes in `services/api/src/routers/v1/calendar_router.py`:
    - `GET /calendars/{id}/members`
    - `PATCH /calendars/{id}/members/{user_id}`
    - `DELETE /calendars/{id}/members/{user_id}`
    - `POST /calendars/{id}/leave`

- [x] **Task 8 — Tests** (AC: 10)
  - [x] Create `services/api/tests/test_calendar_member_management.py`.
  - [x] Cover the matrix listed in AC #10. Use existing `MockCalendar` / `MockCalendarUser` mocks.

- [x] **Task 9 — Local CI**
  - [x] `npx nx run api:lint`
  - [x] `npx nx run utils:lint` (model change)
  - [x] `npx nx run api:test`
  - [x] `npx nx run migrator:check-models`

### Key Files
- Create: `services/api/src/api/v1/calendar/list_calendar_members.py`
- Create: `services/api/src/api/v1/calendar/update_calendar_member.py`
- Create: `services/api/src/api/v1/calendar/remove_calendar_member.py`
- Create: `services/api/src/api/v1/calendar/leave_calendar.py`
- Modify: `services/api/src/api/v1/calendar/__init__.py`, `services/api/src/routers/v1/calendar_router.py`
- Modify: `libraries/utils/utils/classes/error_code.py` (4 new codes)
- Modify: `libraries/utils/utils/models/calendar_user.py` (Index)
- Create: Alembic migration for the partial unique index
- Create: `services/api/tests/test_calendar_member_management.py`
