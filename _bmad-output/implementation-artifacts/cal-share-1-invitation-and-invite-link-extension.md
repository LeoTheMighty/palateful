# Story cal-share-1: Invitation & invite-link extension for calendar resource_type

Status: ready-for-dev

## Story

As the backend,
I want to accept `resource_type='calendar'` on every invitation and invite-link path,
so that any Flutter-side sharing UI can call the existing endpoints with a new value and get the full behavior — direct invite, email-with-no-account, invite-link, accept, decline, claim, revoke.

## Acceptance Criteria

1. `VALID_ROLES` in `services/api/src/api/v1/invitations/helpers.py` gains `"calendar": {"editor"}`.
2. `check_resource_permission()` gets a `calendar` branch: load the calendar; 404 if archived/not-found; require the caller is the **owner** on `calendar_users` (editors cannot invite — matches recipe-book convention).
3. `create_membership()` gets a `calendar` branch: insert / un-archive a `calendar_users` row with `role='editor'` and `invited_by_id`. Idempotent on already-active member; un-archives + updates role/invited_by_id on archived row.
4. `check_existing_membership()` gets a `calendar` branch: True iff an active `calendar_users` row exists for `(user_id, calendar_id)`.
5. `get_resource_name()` gets a `calendar` branch: returns `calendars.name`.
6. `POST /v1/invitations` with `resource_type='calendar'`, `role_offered='editor'` and a valid target works end-to-end (creates Invitation row, dispatches existing `INVITATION_RECEIVED` push to user targets).
7. `POST /v1/invitations/{id}/accept` on a calendar invitation creates the `calendar_users` row, writes an `Activity` of `action='joined'` with `resource_type='calendar'`, and dispatches the existing `INVITATION_ACCEPTED` push to the inviter.
8. `POST /v1/invite-links` with `resource_type='calendar'` creates a token. `GET /v1/invite-links/{token}` returns calendar name + state + creator info; `POST /v1/invite-links/{token}/join` adds the joiner as editor (or returns `already_member` if active).
9. `POST /v1/invitations/claim` is already resource-type-agnostic — verify it picks up calendar invites by email after signup (regression test).
10. **Archived-membership reactivation**: if a previously-removed user (archived `calendar_users` row) is re-invited and accepts, their row un-archives with `role='editor'` and `invited_by_id` set to the new inviter. `check_existing_membership` returns False for archived rows so re-invite does not collide with `INVITATION_ALREADY_MEMBER` (248).
11. **Push-payload completeness**: the `INVITATION_RECEIVED` push includes `resource_name` in its `data` payload (in addition to the body string) so a deep-link lands with a name-resolved title without an app round-trip. Trivial addition; covers all resource types, not just calendar.
12. Tests in `test_invitation_calendar_resource.py` cover: send-by-user-id, send-by-username, send-by-email-no-account → claim → list-received, invite-link create + preview + join, send-as-editor-forbidden (non-owner invite attempt → 403), send-duplicate-invite → 242, self-invite → 247, **re-invite-of-previously-removed-member-reactivates-archived-row**, **push-payload-includes-resource-name**, **calendar-not-found → 404 on send and link create**, **rate-limit-applies-across-resource-types** (mix of recipe-book + calendar invites still hits 30/day cap).

## Tasks / Subtasks

- [x] **Task 1 — Extend invitation helpers for calendar** (AC: 1–5)
  - [x] Add `"calendar": {"editor"}` to `VALID_ROLES`.
  - [x] Add a `calendar` branch to `check_resource_permission`: load `Calendar` (404 `CALENDAR_NOT_FOUND` if missing/archived); fetch `CalendarUser` for `(user_id, calendar_id, archived_at IS NULL)`; if missing or `role != 'owner'`, raise 403 `CALENDAR_ACCESS_DENIED`.
  - [x] Add a `calendar` branch to `check_existing_membership`: query `CalendarUser` for `(user_id, calendar_id, archived_at IS NULL)` and return bool.
  - [x] Add a `calendar` branch to `create_membership`: same upsert pattern as the other resource types — fetch existing row by `(user_id, calendar_id)`; if archived, un-archive + update role + invited_by; else insert new with `role='editor'`. End with `db.flush()`.
  - [x] Add a `calendar` branch to `get_resource_name`: return `calendars.name`.

- [x] **Task 2 — Push-payload audit (`resource_name` in `data`)** (AC: 11)
  - [x] In `services/api/src/api/v1/invitations/send_invitation.py`, add `"resource_name": resource_name or ""` to the `INVITATION_RECEIVED` push `data` dict. Body string already references `resource_name`; only the data payload is missing it.
  - [x] In `services/api/src/api/v1/invitations/accept_invitation.py`, add `"resource_name": resource_name or ""` to the `INVITATION_ACCEPTED` push `data` dict (consistency).

- [x] **Task 3 — Tests** (AC: 12)
  - [x] Create `services/api/tests/test_invitation_calendar_resource.py`. Use the existing `client + mock_db + mock_user` fixtures and the `MockCalendar` / `MockCalendarUser` mocks already in `conftest.py`.
  - [x] Cover the cases listed in AC #12.

- [x] **Task 4 — Local CI** (lint + tests + check-models)
  - [x] `npx nx run api:lint`
  - [x] `npx nx run api:test`
  - [x] No model changes — `check-models` not required.

## Implementation Notes

- **No schema migration**: the existing `calendar_users` composite PK + the upsert pattern in `create_membership` matches what other resource types do. The `calendar_user.py` handoff note about a possible PK rework is deferred — the upsert path works as-is.
- **No router changes**: `POST /v1/invitations`, accept/decline/revoke, and the four invite-link routes are all parameterized by `resource_type`. Once `VALID_ROLES['calendar']` exists, validation accepts the new value and the rest of the chain just runs.
- **`claim_invitations.py` is type-agnostic**: it filters on email + status, never on resource_type. Calendar email invites are picked up by the existing claim path with no changes.
- **Inviter must be owner, not editor**: matches the recipe-book convention. Editor role on calendars grants meal-event edit rights but not member management — that's the cal-share-2 contract too.
- **Calendars don't have `is_shared`** in the same way recipe-books / shopping-lists do — they have `is_shared: bool` but it's not flipped on first invite (calendars are conceptually owner-shareable from creation). Don't touch the flag in `create_membership` for calendar resources.

### Key Files
- Modify: `services/api/src/api/v1/invitations/helpers.py`
- Modify: `services/api/src/api/v1/invitations/send_invitation.py` (push data payload)
- Modify: `services/api/src/api/v1/invitations/accept_invitation.py` (push data payload)
- Create: `services/api/tests/test_invitation_calendar_resource.py`
