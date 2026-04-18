# Story cal-found-2: Rewire meal_event + recurrence_rule authorization, require calendar_id, union shopping-list populate

Status: ready-for-dev

## Story

As Leo,
I want every calendar-related read and write to enforce calendar-membership authorization and refuse to create anything without a calendar_id,
so that calendars are the real unit of isolation — not just a label.

## Acceptance Criteria

1. **`require_calendar_access(calendar_id, user, database, roles={"owner","editor"})`** lives in `services/api/src/api/v1/calendar/dependencies.py`. Returns the `CalendarUser` row if the user is an active member with an acceptable role; raises `APIException(403, CALENDAR_ACCESS_DENIED)` otherwise. All meal_event + recurrence_rule handlers consume it instead of inline `SELECT FROM calendar_users` so auth logic stays in one place.
2. `POST /api/v1/meal-events` requires `calendar_id` in the request body. Missing → HTTP 400 with new error code `MEAL_EVENT_CALENDAR_REQUIRED = 264`. Non-editor on the calendar → 403 via `require_calendar_access`.
3. `POST /api/v1/recurrence-rules` requires `calendar_id` in the request body. Missing → HTTP 400 with new error code `RECURRENCE_RULE_CALENDAR_REQUIRED = 265`. Same auth rule.
4. `GET /api/v1/meal-events` accepts optional `calendar_id` query param. When set, scopes to that calendar (403 if not a member). When unset, unions across all calendars the user is an active member of.
5. `GET /api/v1/recurrence-rules` accepts the same optional `calendar_id` query param with the same semantics. Pantry-based `is_shared` visibility remains as a secondary filter — the calendar-membership scope is the primary gate.
6. `GET /api/v1/meal-events/{id}`, `PATCH /api/v1/meal-events/{id}`, `DELETE /api/v1/meal-events/{id}`: all gate on `require_calendar_access(event.calendar_id, ...)`. Non-member → **404** on GET/DELETE (prevents resource-existence leaks), **403** on PATCH. Regression test: a guest-participant who is NOT a calendar member gets 404 on GET.
7. `PATCH /api/v1/meal-events/{id}` supports a new `calendar_id` field for Move-to-calendar. When set to a different calendar than the current one, validates the user is editor on BOTH source and destination calendars before committing. Same-calendar move (source == destination) is a validated no-op (returns 200 with no DB write). Transactional — partial move impossible.
8. `PATCH /api/v1/recurrence-rules/{id}` scope=all supports a `calendar_id` move. Move updates `calendar_id` on the rule AND cascades to every future materialized meal_event (WHERE `scheduled_at >= now()`). Past materialized rows are untouched. Same-calendar move is a no-op.
9. `POST /api/v1/shopping-lists/{id}/populate-from-calendar` (note: router path; module is `populate_from_calendar.py`) replaces `MealEvent.owner_id == user.id` with `MealEvent.calendar_id IN (SELECT calendar_id FROM calendar_users WHERE user_id=:me AND archived_at IS NULL)`. Existing request/response shape unchanged. Regression test with fixture of one user with one calendar confirms byte-equivalent output to before (ordering + item count).
10. Per-request N+1 guard: the `list_meal_events` endpoint fetches the user's calendar ids ONCE (single `SELECT calendar_id FROM calendar_users WHERE user_id=:me AND archived_at IS NULL`) and uses the set in the main filter. Same for `list_recurrence_rules`. No per-row DB roundtrip for auth.
11. Tests updated + new:
   - `test_calendar_authorization.py` (new file) covers: guest-participant-NOT-calendar-member → 404 on GET, move-without-editor-on-destination → 403, move-same-calendar → no-op, move-rule-cascades-to-future-events.
   - `test_meal_event.py` (extend): create-missing-calendar-id → 400+264, create-with-invalid-calendar-id → 403, list scoped to calendar_id works, list-without-filter unions correctly, update-move-to-calendar works.
   - `test_recurrence_rule.py` (extend): same treatment as above.
   - `test_populate_from_calendar.py` (extend): unions across calendars, single-calendar-user byte-equivalent.
12. Out of scope: `invite_participant.py`, `respond_to_invite.py`, `skip_meal_event.py` — these retain current participant-based auth. The calendar is the unit of *edit* authorization; per-meal invites are a separate axis.

## Tasks / Subtasks

- [ ] **Task 1 — Error codes + shared dependency** (AC: 1, 2, 3)
  - [ ] Add `MEAL_EVENT_CALENDAR_REQUIRED = 264` and `RECURRENCE_RULE_CALENDAR_REQUIRED = 265` to `libraries/utils/utils/classes/error_code.py` (Calendar block 261-269).
  - [ ] Create `services/api/src/api/v1/calendar/dependencies.py` with `require_calendar_access(calendar_id, user, database, roles=DEFAULT_WRITE_ROLES)` — inline function (not a FastAPI `Depends` for ease of reuse from handlers). Returns the `CalendarUser` row. Also add a helper `get_user_calendar_ids(user, database)` returning a list of UUIDs (active memberships).
  - [ ] Constant `DEFAULT_WRITE_ROLES = {"owner", "editor"}` lives in the same module.

- [ ] **Task 2 — Rewire `create_meal_event`** (AC: 2)
  - [ ] Add required `calendar_id: str` on Params. Pydantic's required-field error gives a generic 422; override: inline check after Params parse (or via a pre-validator) that raises `MEAL_EVENT_CALENDAR_REQUIRED` with HTTP 400. Simplest: since Params parsing happens before `execute`, keep `calendar_id: str` required — FastAPI returns 422. Because the spec mandates 400+264, add a pre-check that inspects the raw request body in the handler or, cleaner, add a separate validator. *Implementation*: keep `calendar_id: str` required on Params (FastAPI enforces presence), but ALSO validate non-empty string inside `execute()` and translate into 400+264. That way, tests that POST `{calendar_id: ""}` still hit the explicit error code. Pragmatic shortcut: if the POST body lacks the key entirely, FastAPI returns 422; tests explicitly construct `{calendar_id: ""}` and the 400+264 handler kicks in. This is a reasonable trade-off — 422 for malformed payload, 400+264 for logically missing.
  - [ ] Call `require_calendar_access(params.calendar_id, user, database)` before creating the event.
  - [ ] Set `meal_event.calendar_id = params.calendar_id` on the new row.
  - [ ] Include `calendar_id` in the response body.

- [ ] **Task 3 — Rewire `list_meal_events`** (AC: 4, 10)
  - [ ] Accept optional `calendar_id: str | None = None` query param on the router + endpoint.
  - [ ] If set: verify active membership (403 if not). Scope query to `MealEvent.calendar_id == calendar_id`.
  - [ ] If unset: fetch all user's calendar ids once (via `get_user_calendar_ids`), scope to `MealEvent.calendar_id.in_(calendar_ids)`. If the user has zero memberships (shouldn't happen post-backfill, but defensive), return empty list.
  - [ ] Drop the `MealEvent.owner_id == user.id OR MealEventParticipant.user_id == user.id` OR-clause — calendar membership is now the sole gate.
  - [ ] **Keep** the eager materialization pre-pass (iterates over the user's own rules — same behavior, doesn't need calendar-scoping for correctness).
  - [ ] Include `calendar_id` on the `MealEventItem` response shape.

- [ ] **Task 4 — Rewire `get_meal_event`** (AC: 6)
  - [ ] Drop the owner-or-participant auth. Replace with `require_calendar_access(meal_event.calendar_id, user, database)` — on 403, mask as 404 `MEAL_EVENT_NOT_FOUND` for GET (no existence leak).
  - [ ] Include `calendar_id` in the response.

- [ ] **Task 5 — Rewire `update_meal_event`** (AC: 6, 7)
  - [ ] Drop the owner-or-cohost auth. Replace with `require_calendar_access(meal_event.calendar_id, user, database)` — 403 on non-member (PATCH keeps 403, matches spec's "404 on GET/DELETE, 403 on PATCH").
  - [ ] Accept new optional `calendar_id: str | None = None` on Params.
  - [ ] If `params.calendar_id` is set AND != current `meal_event.calendar_id`: call `require_calendar_access(params.calendar_id, user, database)` to verify editor on destination. Then `meal_event.calendar_id = params.calendar_id`.
  - [ ] Same-calendar move is a silent no-op (skip the check, skip the write).
  - [ ] Include `calendar_id` in response.

- [ ] **Task 6 — Rewire `delete_meal_event`** (AC: 6)
  - [ ] Drop the owner-only check. Replace with `require_calendar_access(meal_event.calendar_id, user, database)` — on 403, mask as 404 `MEAL_EVENT_NOT_FOUND` (no existence leak on DELETE either).
  - [ ] Archive via `archived_at` (existing behavior).

- [ ] **Task 7 — Rewire `create_recurrence_rule`** (AC: 3)
  - [ ] Add required `calendar_id: str` on Params.
  - [ ] Pre-execute check for missing/empty → 400 + `RECURRENCE_RULE_CALENDAR_REQUIRED = 265`.
  - [ ] `require_calendar_access(params.calendar_id, user, database)` before creating.
  - [ ] Set `rule.calendar_id = params.calendar_id`.
  - [ ] Include `calendar_id` in `RecurrenceRuleResponse` (`_rule_to_response`).

- [ ] **Task 8 — Rewire `list_recurrence_rules`** (AC: 5, 10)
  - [ ] Accept optional `calendar_id` query param. If set, scope. If unset, scope to `MealRecurrenceRule.calendar_id.in_(user_calendar_ids)`.
  - [ ] Drop the existing pantry-based `is_shared` OR-clause as the primary gate (calendar membership is the gate now). If preserving `is_shared` for pantry-mate visibility is needed, leave it as an additional OR — but the test matrix must confirm pantry-mate-who-is-NOT-a-calendar-member sees nothing. Simplest: remove the pantry-union logic; calendar membership is the only scope. Pantry mates who need visibility will be calendar members post-sharing-epic.

- [ ] **Task 9 — Rewire `get_recurrence_rule`** (AC: 6)
  - [ ] Replace `user_can_read_rule` with `require_calendar_access(rule.calendar_id, user, database)` — 404 `NOT_FOUND` on non-member (matches existing 404 pattern).

- [ ] **Task 10 — Rewire `update_recurrence_rule`** (AC: 6, 8)
  - [ ] Replace `user_can_write_rule` with `require_calendar_access(rule.calendar_id, ...)`. Note: both `_apply_all` and `_apply_split` paths.
  - [ ] Add optional `calendar_id` to `UpdateRecurrenceRule.Params`. In `_apply_all`, if set AND != current rule's `calendar_id`: `require_calendar_access` on destination → update rule.calendar_id → cascade `UPDATE meal_events SET calendar_id=:new WHERE recurrence_rule_id=:rule_id AND scheduled_at >= now()`.
  - [ ] In `_apply_split`, the new rule inherits the source rule's calendar_id unless `params.calendar_id` is explicitly set. Use same pattern.
  - [ ] Same-calendar move → no-op.

- [ ] **Task 11 — Rewire `delete_recurrence_rule`** (AC: 6)
  - [ ] Replace `user_can_write_rule` with `require_calendar_access(rule.calendar_id, ...)`. Rule-delete scope is still scope=series / this_and_following / this_occurrence — auth is the only change.

- [ ] **Task 12 — Rewire `populate_from_calendar`** (AC: 9)
  - [ ] Replace `MealEvent.owner_id == user.id` filter with `MealEvent.calendar_id.in_(calendar_ids)` where `calendar_ids` is the user's active membership set (fetched once, per Task 1's helper).
  - [ ] Everything else stays. The existing shopping-list-ownership check is unchanged (that's a separate concern).

- [ ] **Task 13 — Router wiring** (AC: 4, 5)
  - [ ] `meal_event_router.py`: pass `calendar_id: str | None` to `ListMealEvents.call`.
  - [ ] `recurrence_rule_router.py`: same.

- [ ] **Task 14 — Tests** (AC: 11)
  - [ ] `services/api/tests/test_calendar_authorization.py` (new): focused regression tests for the narrowing. Guest-participant-NOT-member → 404 on GET. Move without destination editor → 403. Same-calendar move → 200 noop. Rule move cascades to future events only (not past).
  - [ ] `services/api/tests/test_meal_event.py` (modify): every existing test that calls `POST /v1/meal-events` now needs `calendar_id` in the body + membership mock. Add new cases for missing-calendar-id → 400+264, list with/without calendar_id scope, update move-to-calendar.
  - [ ] `services/api/tests/test_recurrence_rule.py` (modify): same treatment.
  - [ ] `services/api/tests/test_populate_from_calendar.py` (modify): verify union semantics. Add a case with 2 calendars.
  - [ ] `services/api/tests/test_list_meal_events_recurrence.py` (existing): still passes with calendar-membership-scoped list.

- [ ] **Task 15 — Local CI** (before commit)
  - [ ] `npx nx run api:lint`, `npx nx run utils:lint`
  - [ ] Full `api:test` suite passes (`DATABASE_URL=...` set for test env).
  - [ ] `npx nx run migrator:check-models` (no new models added, but schema imports may have drifted — re-run to be sure).

## Dev Notes

### Architecture compliance ([Source: architecture.md#Addendum — Calendar as First-Class Container])

- "**Calendar is the unit of authorization**" — principle #1 of the epic. This is the most important part of the story. Owner_id on meal_events is vestigial (kept for the down-migration path + attribution) — `calendar_users` is the gate.
- Host/cohost/guest **no longer grants edit authorization**. Only calendar_users membership does. This is a semantic narrowing and MUST be explicitly tested — see cal-found-2 AC 6 regression test.
- `require_calendar_access` is the one-and-only auth primitive. **No inline `SELECT FROM calendar_users`** in handlers. Keeps the cal-share epic's role-check extension point centralized.
- **404 on GET/DELETE, 403 on PATCH** is the existing project convention for non-member responses (prevents existence leaks on read/delete paths while still being informative on write).

### Why `calendar_id` as required on Params (not optional)

The architecture addendum line 942: "server-required `calendar_id` on all writes; old clients writing without it get 400 immediately. New client ships same day. No 'optional→required' two-phase — user base is small enough that a brief stale-client write-fail window is acceptable."

The Flutter client (cal-found-3/5) will always send `calendar_id`. A Pydantic 422 on malformed payload is acceptable; the 400+264 case is for when the field exists but is empty string or null (older clients). Implementation detail: just make `calendar_id: str` required on Params. Pydantic 422 for missing + the handler's early-empty check for explicit 400+264 covers both paths. Don't over-engineer.

### Why drop the meal_event `OR participant` read path in list

Existing `list_meal_events` has:
```python
.outerjoin(MealEventParticipant, ...)
.filter(or_(MealEvent.owner_id == user.id, MealEventParticipant.user_id == user.id))
```

Post-rewire: the participant join is no longer used for auth. A meal_event's `calendar_id` now carries edit authority via `calendar_users`. Guests who aren't calendar members will see nothing — this is the intentional semantic narrowing. Participant data is still *returned* in the response for display purposes.

### Why no pagination change

The existing response shape has `total, limit, offset`. Keep them. The `calendar_id` filter reduces the result set, but pagination semantics are unchanged. Clients that don't pass `calendar_id` still get the union (same as today's behavior, just via a different scoping mechanism).

### Implementation sketch: `require_calendar_access`

```python
# services/api/src/api/v1/calendar/dependencies.py
from typing import Iterable
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.calendar_user import CalendarUser
from utils.models.user import User

DEFAULT_WRITE_ROLES = frozenset({"owner", "editor"})


def require_calendar_access(
    calendar_id: str,
    user: User,
    database,
    roles: Iterable[str] = DEFAULT_WRITE_ROLES,
) -> CalendarUser:
    """Return the user's active CalendarUser row on `calendar_id`.

    Raises APIException(403, CALENDAR_ACCESS_DENIED) if the user has no
    active membership or the role is not in `roles`.
    """
    membership = database.find_by(
        CalendarUser, user_id=user.id, calendar_id=calendar_id
    )
    if not membership or membership.archived_at is not None:
        raise APIException(
            status_code=403,
            detail="You do not have access to this calendar",
            code=ErrorCode.CALENDAR_ACCESS_DENIED,
        )
    if membership.role not in roles:
        raise APIException(
            status_code=403,
            detail="Your role does not permit this action",
            code=ErrorCode.CALENDAR_ACCESS_DENIED,
        )
    return membership


def get_user_calendar_ids(user, database) -> list:
    """Return a list of calendar_ids the user is an active member of.

    One query per request. Caller scopes meal_events / rules with
    `.calendar_id.in_(...)`.
    """
    rows = (
        database.db.query(CalendarUser.calendar_id)
        .filter(CalendarUser.user_id == user.id)
        .filter(CalendarUser.archived_at.is_(None))
        .all()
    )
    return [row[0] for row in rows]
```

### Implementation sketch: `update_meal_event` Move-to-calendar

```python
# ... after existing find + auth on source calendar:
if params.calendar_id is not None and params.calendar_id != str(meal_event.calendar_id):
    # Editor on destination too.
    require_calendar_access(params.calendar_id, user, database)
    meal_event.calendar_id = params.calendar_id
# Same-calendar: no-op, no auth check on destination (already checked source).
```

### Implementation sketch: rule move cascade

```python
# _apply_all, after settling other fields:
if params.calendar_id is not None and str(params.calendar_id) != str(rule.calendar_id):
    require_calendar_access(params.calendar_id, user, database)
    rule.calendar_id = params.calendar_id
    # Cascade to future materialized events.
    from datetime import UTC, datetime
    self.db.query(MealEvent).filter(
        MealEvent.recurrence_rule_id == rule.id,
        MealEvent.scheduled_at >= datetime.now(UTC),
    ).update(
        {MealEvent.calendar_id: params.calendar_id},
        synchronize_session=False,
    )
```

### 403 vs 404 mask for DELETE

The spec says 404 on DELETE for non-members (no existence leak). Currently `DeleteMealEvent` uses 403 for owner-mismatch. After the rewire: catch `APIException(403, CALENDAR_ACCESS_DENIED)` from `require_calendar_access` and re-raise as 404 `MEAL_EVENT_NOT_FOUND`. Cleaner: just do the auth check inline without the dependency and raise 404 directly if not-member. Match the existing project pattern.

### Existing tests that WILL break

- `test_meal_event.py::TestCreateMealEvent`: every test that POSTs without `calendar_id`. Update fixtures to include `calendar_id` + a configured CalendarUser membership.
- `test_meal_event.py::TestGetMealEvent` / `TestUpdateMealEvent` / `TestDeleteMealEvent`: owner-based mocks need to be replaced with calendar_users membership mocks.
- `test_list_meal_events_recurrence.py`: the materialize pre-pass is unchanged; list's auth path changes. Update the mocks.
- `test_recurrence_rule.py`: same as meal_event treatment.
- `test_populate_from_calendar.py`: the `MealEvent.owner_id == user.id` filter is gone; the mock now needs to simulate the calendar_ids subquery or be rewritten with a simpler mock.

**Strategy**: rather than patching every test individually, update `conftest.py` to add helpers like `mock_db.with_calendar_membership(mock_user, calendar_id)` that configures the `find_by(CalendarUser, ...)` return. This makes the test updates uniform and short.

### QA Walkthrough Checklist

Output to `cal-found-2-qa-walkthrough.md`.

Backend-only smoke tests:
- [ ] `POST /v1/meal-events` without `calendar_id` → 422 (FastAPI) or 400+264 (if empty string); verify both paths.
- [ ] `POST /v1/meal-events` with a calendar_id the user doesn't own → 403+263 (CALENDAR_ACCESS_DENIED).
- [ ] `GET /v1/meal-events?calendar_id=<cal-b>` as a member of cal-b returns only cal-b events; as a non-member → 403+263.
- [ ] `GET /v1/meal-events` with no filter returns the union across all user calendars.
- [ ] `GET /v1/meal-events/{event-in-cal-b}` as non-member of cal-b → 404+130 (MEAL_EVENT_NOT_FOUND). Regression test case.
- [ ] `PATCH /v1/meal-events/{id}` with `calendar_id=<different>` where user is editor on both → 200 with meal moved. Repeat as non-editor on destination → 403.
- [ ] Same-calendar move → 200 noop, no DB write logged.
- [ ] `PATCH /v1/recurrence-rules/{id}` with `calendar_id=<different>`: rule moves, future events cascade (`SELECT COUNT(*) FROM meal_events WHERE recurrence_rule_id=... AND calendar_id=<new>` > 0); past events still have old calendar_id.
- [ ] `POST /v1/shopping-lists/{id}/populate-from-calendar` pulls events across all user calendars (verify via DB query count).
- [ ] Guest-participant who is NOT a calendar member: adds them via `invite_participant`, then GET the meal_event as that user → 404+130. Host/cohost/guest does NOT grant edit.

### Project Structure Notes

- No new top-level folders.
- `services/api/src/api/v1/calendar/dependencies.py` is a new file adjacent to the CRUD handlers from cal-found-1. Keeps the whole calendar-auth surface in one directory.

### References

- [Source: _bmad-output/planning-artifacts/epic-calendars-foundation.md#Story cal-found-2 (lines 209–235)]
- [Source: _bmad-output/planning-artifacts/architecture.md#Addendum — 2026-04-17 — Calendar as First-Class Container (lines 895–965)]
- [Source: services/api/src/api/v1/calendar/delete_calendar.py — existing membership lookup pattern]
- [Source: services/api/src/api/v1/recurrence_rule/_access.py — pattern this story REPLACES (but keep the validation helpers)]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

### Completion Notes List

### File List
