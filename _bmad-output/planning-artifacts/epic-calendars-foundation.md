<!-- refined via party-mode 2026-04-17 -->
# Epic: Calendars — Foundation (first-class calendar container, switcher, backfill)

## Overview

Today every `meal_event` and `meal_recurrence_rule` is scoped to a user's implicit "calendar" via `owner_id` alone. There is no container, no way to own multiple calendars, no way to swap between them, no way to move a meal from one logical calendar to another. This epic introduces **Calendar** as a first-class resource — a container that every meal and every recurrence rule belongs to, via a mandatory `calendar_id` FK — and lands the foundation a user touches on day one: a Calendar-tab switcher, create/rename/delete flows, a plan-meal "Calendar:" picker, and a move-to-calendar action.

This epic ships **standalone**: every existing user gets a default calendar named "My Calendar" via a one-time backfill migration, every existing meal/rule lands inside it, the switcher shows one entry on day one, and the app works exactly like today with zero user action. The moment a user taps **New Calendar**, the value is visible.

The next epic (`epic-calendars-sharing`) adds the "invite someone with full edit rights" layer on top of this foundation. Sharing is not in this epic — a shared calendar with no way to invite anyone would be meaningless.

**Goal:** When this epic ships, Leo can own "My Calendar" + "Meal Prep" + "Date Nights" and switch between them from the Calendar tab header in two taps. Each calendar is isolated; scheduling a meal on Meal Prep doesn't put it on My Calendar. He can move a mis-scheduled meal between calendars, rename a calendar, and delete one. Every pre-existing meal is exactly where it was, under "My Calendar."

## End-User Flow

1. Leo updates the app. Nothing visibly changed: every meal he had before is still on the Calendar tab.
2. The tab header now reads **"My Calendar ▾"** where before it read "Calendar" (or similar).
3. He taps the chevron → a bottom sheet slides up with a single list row: **My Calendar · default · 0 others**. Below the list: a **+ New Calendar** action.
4. He taps **+ New Calendar** → small dialog: "Name" (required, autofocus) + "Description (optional)" + Create button.
5. He types "Meal Prep" → Create. The sheet dismisses; the header now reads **"Meal Prep ▾"**; the grid is empty (contextual empty state: "No meals on Meal Prep yet. Tap + to plan one.").
6. He taps the FAB → plan-meal sheet opens. A new row near the top reads **"Calendar: Meal Prep"** with a chevron — pre-selected to the active calendar, and the picker shows only calendars he can write to (in this epic, only owned; sharing epic adds editor-access). If he wants to add the meal to My Calendar instead, he taps that row → calendar picker → picks "My Calendar" → returns to the plan-meal sheet with the Calendar row updated. When a user has only one writable calendar, this row is **hidden entirely** (not shown-disabled) — it's noise for the 80% solo-calendar case. (Default is always "currently-active calendar.")
7. He finishes the plan-meal sheet → the meal saves to whichever calendar the row showed. Calendar grid reloads.
8. From any meal detail sheet (tap a tile) → a new **Move to calendar** row. Tap → calendar picker → pick destination → meal moves, calendar grid reloads to whichever calendar the user was viewing.
9. From the switcher bottom sheet, tapping the **chevron on a calendar row** opens **Calendar Settings** (rename, edit description, delete). The switcher **row body** and **trailing chevron** are distinct hit targets (≥40px apart) — tapping the row activates that calendar, tapping the chevron opens settings. Delete prompts "Delete Meal Prep? All meals on this calendar will be archived. This cannot be undone." (Copy is scaffolded for the sharing-epic variant: "Delete 'X'? N members will lose access. All meals will be archived." — activated once members > 1.) Confirm → calendar + its meals archive. If the user deletes the calendar they were viewing, the switcher falls back to the user's **default** calendar; if the default was the deletion target (only possible when it's not the last calendar), the switcher falls back to the **most recently created** remaining calendar.
10. If Leo tries to delete his only remaining calendar, the confirm button is disabled with helper text: "You can't delete your only calendar."

**What does not change:** the week grid, the plan-meal-sheet layout below the new Calendar row, the meal-detail-sheet below the new Move row, recurrence rules (they just gain a calendar_id under the hood and a Calendar row in the recurrence-create UI), the recipe "Plan for…" flow, the shopping-list `auto_populate_from_calendar` behavior (still unions across all accessible calendars — matters more in the sharing epic).

## Frontend Changes

Touches `app/lib/features/calendar/` (heavy), `app/lib/features/profile/` (tiny), and adds one repo/provider pair.

- **`models/calendar.dart`** (new): `Calendar` class — id, name, description, isDefault, isShared, ownerId, memberCount (derived), createdAt. Plus `CalendarMembership` or equivalent for the switcher subtitle line.
- **`services/calendar_service.dart`** (new): API client — `listCalendars()`, `createCalendar(name, description?)`, `getCalendar(id)`, `updateCalendar(id, {name?, description?})`, `deleteCalendar(id)`.
- **`providers/active_calendar_provider.dart`** (new, Riverpod): holds the currently-selected calendar id. Hydrates from local storage (via `shared_preferences`) on app start; persists every change. Defaults to the user's default calendar if no prior selection exists or the stored id is no longer accessible.
- **`widgets/calendar_switcher_header.dart`** (new): the "My Calendar ▾" chip/pill that replaces the static header on `calendar_screen.dart`.
- **`widgets/calendar_switcher_sheet.dart`** (new): the bottom sheet showing "My Calendars" list + "+ New Calendar" action. Tapping a calendar row sets `activeCalendarProvider` and dismisses; the per-row chevron opens Calendar Settings.
- **`widgets/calendar_create_dialog.dart`** (new): name + optional description form.
- **`widgets/calendar_settings_sheet.dart`** (new): rename, edit description, delete. Rename inline-edits (autosave on blur); delete prompts confirmation. Members section is scaffolded but empty with a "Sharing coming soon" helper — the sharing epic fills it in.
- **`calendar_screen.dart`** (modify): swap the static app-bar title for `CalendarSwitcherHeader`; consume `activeCalendarProvider`; pass the active calendar id to `listMealEvents(calendarId, start, end)`. Empty-state copy updates when the active calendar has zero meals: "No meals on [name] yet."
- **`widgets/plan_meal_sheet.dart`** (modify): insert a **Calendar** row at the top of the form (above the existing Date row) showing the active calendar name + chevron. Tapping opens a calendar-only picker (writable calendars the user has: owner or editor — in this epic, only owned calendars qualify since sharing doesn't exist yet). Pass the selected `calendar_id` to `createMealEvent` / `createRecurrenceRule`.
- **`widgets/meal_detail_sheet.dart`** (modify): add a **Move to calendar** row among the secondary actions. Tap opens the same calendar picker; on select, calls `updateMealEvent(mealId, {calendarId: newId})`, dismisses the sheet, reloads.
- **`widgets/recurrence_field.dart`** (modify, minor): rule-create also respects the active calendar (no extra UI — the plan-meal sheet already owns the Calendar row).
- **`features/profile/profile_screen.dart`** (modify, minor): reserves the "Shared Calendars" row position with a disabled/hidden scaffold; sharing epic turns it on.
- **Tests**: widget tests for switcher, create dialog, settings sheet, move action; provider test for `activeCalendarProvider` (persistence + fallback-to-default).

No new navigation route. All calendar UI lives inside the Calendar tab (modal sheets). No change to `go_router`.

## Backend Changes

Adds two tables, one router, eight handlers, one backfill migration, one trigger on user creation.

- **`libraries/utils/utils/models/calendar.py`** (new): `Calendar` SQLAlchemy model with columns per the architecture addendum. Standard `BaseModel` inheritance (id, created_at, updated_at, archived_at).
- **`libraries/utils/utils/models/calendar_user.py`** (new): `CalendarUser` join model — composite PK `(calendar_id, user_id)`, `role` enum `owner|editor`, `invited_by_id` (nullable), `last_opened_at`, `archived_at`. Inherits `JoinsBase` (matches `RecipeBookUser`).
- **`libraries/utils/utils/models/meal_event.py`** (modify): add `calendar_id` UUID FK (nullable initially; tightened to NOT NULL after backfill step of the migration). Index on `(calendar_id, scheduled_at)`.
- **`libraries/utils/utils/models/meal_recurrence_rule.py`** (modify): same — add `calendar_id` UUID FK (nullable → NOT NULL). Index on `(calendar_id)`.
- **`libraries/utils/utils/models/__init__.py`** (modify): register the two new models.
- **`services/migrator/migrations/versions/<new>_add_calendars.py`** (new): the 8-step backfill migration described in the architecture addendum. Creates tables → adds nullable FKs → backfills default calendars per user → backfills `calendar_id` on existing meal_events and recurrence rules → tightens FKs to NOT NULL → integrity check (abort if NULL remains).
- **`services/api/src/api/v1/calendar/`** (new handler directory): `create_calendar.py`, `get_calendar.py`, `list_calendars.py`, `update_calendar.py`, `delete_calendar.py`. All follow the existing `Endpoint`-subclass pattern. Member management handlers (list/update/remove member) are stubbed in this epic for reuse by the sharing epic but only owner-role endpoints are wired up for now; non-owner paths return 404-as-not-found.
- **`services/api/src/routers/v1/calendar_router.py`** (new): registers under `/api/v1/calendars`.
- **`services/api/src/schemas/calendar.py`** (new): request/response shapes — `CalendarCreateRequest`, `CalendarUpdateRequest`, `CalendarResponse`, `CalendarMemberResponse` (used by sharing epic).
- **`services/api/src/api/v1/meal_event/*.py`** (modify, every file):
  - `create_meal_event.py`: accept and require `calendar_id` on the request. Authorization: reject if the user isn't owner/editor on that calendar.
  - `list_meal_events.py`: accept an optional `calendar_id` query param. When set, scope the query to that calendar_id. When unset (used by `PopulateFromCalendarRange` today), scope to `calendar_id IN (SELECT ... FROM calendar_users WHERE user_id = :me AND archived_at IS NULL)`.
  - `get_meal_event.py`, `update_meal_event.py`, `delete_meal_event.py`: rewrite permission checks to consult `calendar_users` membership on the event's calendar_id. Host/cohost/guest `meal_event_participants` are no longer consulted for *edit* authorization but are still returned in responses.
  - `update_meal_event.py`: accept an optional `calendar_id` in the update payload to support **Move to calendar**. Rewrite: validate user is editor on source AND destination calendars before committing.
- **`services/api/src/api/v1/recurrence_rule/*.py`** (modify, every file): same treatment — require `calendar_id` on create, scope listing by `calendar_id` query param, rewrite auth to `calendar_users` membership. Move-to-calendar on a rule is symmetric.
- **`services/api/src/api/v1/shopping_list/populate_from_calendar_range.py`** (modify): replace the owner-scoped `meal_events` WHERE clause with a `calendar_id IN (...)` subquery matching the active `calendar_users` memberships. No API shape change.
- **User-provisioning flow** (`services/api/src/api/v1/user/<wherever user-first-seen logic lives>`, likely the Auth0 JWT handler): on first-ever creation of a `users` row, atomically create a default `calendars` row (`name='My Calendar'`, `is_default=true`) and a `calendar_users` row (`role='owner'`).
- **Tests** (new + modifications):
  - `test_calendar_router.py`: create + list + get + update + delete + default-not-deletable-alone + cannot-delete-if-only-calendar.
  - `test_backfill_migration.py` (or migration-level assertion inside the migration file): verifies every user has exactly one default calendar + every meal_event has a calendar_id + every rule has a calendar_id.
  - `test_meal_event_router.py`: extend existing tests — create requires `calendar_id`, list scopes correctly, update supports move-to-calendar, delete + get + update check calendar_users membership, host/cohost/guest no longer grants edit access (regression test).
  - `test_recurrence_rule_router.py`: same treatment as meal_event.
  - `test_populate_from_calendar_range.py`: confirms the shopping-list populate now unions across owned calendars (all user's calendars visible).
  - `test_user_provisioning.py` (or extend whichever test covers user creation): verifies a freshly-created user immediately has a default calendar.

## Infrastructure Changes

- **Migration**: one alembic revision (new tables + two FK columns + 8-step backfill + integrity check + NOT NULL tightening). Runs through the existing `migrator` profile (`docker compose --profile migrate up migrator`). Reversible — down-migration drops the two new FKs and the new tables; data integrity of meal_events/rules is preserved under owner_id.
- **DB snapshot before migration**: mandated by the addendum. Follows the existing pre-deploy backup cadence (NFR14).
- **Worker scheduling**: no change. The existing nightly `advance_recurrence_windows` worker iterates by rule regardless of calendar — it picks up `calendar_id` transparently.
- **Env vars / secrets**: none.
- **Terraform / AWS**: none — no new resources.
- **CI**: covered by the existing `npx nx run api:test` + `migrator:check-models` + `worker:test` matrix.

## Design Principles (refined via party-mode 2026-04-17)

1. **Calendar is the unit of authorization** (backend). Every meal_event / recurrence-rule permission check resolves to `calendar_users (calendar_id, user_id)` — one indexed lookup. Host/cohost/guest participants no longer grant edit access.
2. **`calendar_id` is mandatory post-backfill, enforced via a single `require_calendar_access(resource)` FastAPI dependency** (backend). No inline re-auth in each handler — one `Depends` that resolves `calendar_id` from path/body/resource and rejects on non-membership. Cuts copy-paste drift across ~15 handlers.
3. **Default calendar is sacred; exactly-one is a DB invariant** (backend + PM). Partial unique index `UNIQUE (owner_id) WHERE is_default = true AND archived_at IS NULL` + the delete-last-calendar rejection on the API.
4. **Switcher is the primary affordance; Calendar Settings is a *different* sheet** (UX). The switcher row tap = activate; the trailing chevron = open settings. These MUST be distinct hit targets with ≥40px separation, not a mode switch.
5. **"Active calendar" and "target calendar" are two different pieces of state** (frontend). The plan-meal-sheet form has its own `_targetCalendarId`, seeded from `activeCalendarProvider.read()` once at sheet open. Changing it never mutates the provider.
6. **One calendar picker widget, two consumers** (frontend). `CalendarPickerSheet` is the reusable core; the switcher and the plan-meal-sheet Calendar row both instantiate it with different "on select" callbacks. Switcher sets provider + dismisses; picker sets form state + dismisses.
7. **Move between calendars is transactional and editor-on-both** (backend). 403 if user isn't editor on source AND destination. Same-calendar move is a no-op. Participants + status preserved.
8. **Delete is archive, not purge** (backend). Soft-archive cascades to meals + rules in one transaction. Past meals remain queryable by id.
9. **Backfill migration is idempotent, reversible, and instrumented** (infra + QA). Re-running is a no-op via the partial unique index + NULL-only UPDATEs. Pre-tightening integrity check aborts with an explicit count. Each step logs start/end + row counts to `error_logs` with `service="migrator"` so a prod run is observable.
10. **Sharing UI is scaffolded but not wired** (UX). Settings sheet's Members section shows the *owner* (one row) with a "Sharing coming soon" helper — not an empty section. The switcher body does NOT render an empty "Shared with Me" section on day one; it's code-present but `Visibility(visible: false)` until the sharing epic.
11. **Degenerate "only one calendar" cases never produce dead UI** (UX + QA). Switcher still opens with one row. Move-to-calendar row is *hidden* (not disabled) when user has only one writable calendar. Plan-meal Calendar row is *hidden* in the same case. Empty "You only have one calendar" helpers are noise.
12. **Deploy is atomic via the migration** (infra). Backend + migration ship together with server-required `calendar_id` on all writes; old clients writing without it get 400 immediately. New client ships same day. No "optional→required" two-phase — user base is small enough that a brief stale-client write-fail window is acceptable. Reads never break (server unions across memberships).
13. **Audit-log calendar mutations** (backend). Calendar delete + any member/ownership mutation writes to `error_logs` with `service="audit"` — matches `promote_admin.py`. Error dashboards filter on `service="api"` so audits don't pollute alerting.
14. **Rename uses an explicit Save button, not autosave-on-blur** (UX). Matches recipe-book settings precedent. Avoids debouncing state machines and surprise PATCH-per-keystroke churn on shared calendars once sharing ships.

## File Structure (expected)

```
app/lib/features/calendar/
├── models/
│   └── calendar.dart                      # NEW
├── services/
│   └── calendar_service.dart              # NEW
├── providers/
│   └── active_calendar_provider.dart      # NEW
├── widgets/
│   ├── calendar_switcher_header.dart      # NEW
│   ├── calendar_switcher_sheet.dart       # NEW
│   ├── calendar_create_dialog.dart        # NEW
│   ├── calendar_settings_sheet.dart       # NEW
│   ├── plan_meal_sheet.dart               # MODIFIED — Calendar row
│   ├── meal_detail_sheet.dart             # MODIFIED — Move to calendar row
│   └── recurrence_field.dart              # MODIFIED — respects active calendar
├── calendar_screen.dart                   # MODIFIED — header swap + active-cal consumer
├── models/meal_event.dart                 # MODIFIED — add calendarId
└── services/meal_calendar_service.dart    # MODIFIED — calendar_id on all writes

app/lib/features/profile/
└── profile_screen.dart                    # MODIFIED — scaffold Shared Calendars row

libraries/utils/utils/models/
├── calendar.py                            # NEW
├── calendar_user.py                       # NEW
├── meal_event.py                          # MODIFIED — calendar_id FK
├── meal_recurrence_rule.py                # MODIFIED — calendar_id FK
└── __init__.py                            # MODIFIED — register new models

services/api/src/
├── api/v1/calendar/                       # NEW — full CRUD + member stubs
│   ├── __init__.py
│   ├── create_calendar.py
│   ├── get_calendar.py
│   ├── list_calendars.py
│   ├── update_calendar.py
│   └── delete_calendar.py
├── api/v1/meal_event/                     # MODIFIED — calendar_id on every handler
├── api/v1/recurrence_rule/                # MODIFIED — calendar_id on every handler
├── api/v1/shopping_list/populate_from_calendar_range.py  # MODIFIED — union across calendars
├── routers/v1/calendar_router.py          # NEW
└── schemas/calendar.py                    # NEW

services/migrator/migrations/versions/
└── <YYYYMMDD>_add_calendars.py            # NEW — 8-step backfill migration
```

## Story Map

| # | Story | Priority | Est. Effort | Depends on |
|---|-------|----------|-------------|------------|
| cal-found-1 | Calendar model, calendar_users join, backfill migration, CRUD endpoints | P0 | 1.5 d | — |
| cal-found-2 | Rewire meal_event + recurrence_rule authorization, require calendar_id, populate_from_calendar_range union | P0 | 1.5 d | cal-found-1 |
| cal-found-3 | Flutter switcher (header + bottom sheet + active-calendar provider + persistence) | P0 | 1 d | cal-found-1 |
| cal-found-4 | Flutter create/rename/delete flows + user-provisioning default calendar | P0 | 1 d | cal-found-1 |
| cal-found-5 | Plan-meal-sheet Calendar row + Move-to-calendar action on meal detail + recurrence rule | P1 | 0.5–1 d | cal-found-2, cal-found-3, cal-found-4 |

**Total estimated effort: 5.5–6 days.**

**Sequencing:** cal-found-1 → cal-found-2 ∥ cal-found-3 → cal-found-4 → cal-found-5. cal-found-2 (backend) and cal-found-3 (Flutter switcher) can proceed in parallel once the model + migration land. cal-found-5 depends on cal-found-4 because `CalendarPickerSheet` is factored out during the switcher/settings work and reused in the plan-meal row.

**Optional risk-isolation split**: cal-found-1 can be split into 1a (models + migration + backfill, no API) and 1b (CRUD endpoints + user-provisioning). The migration is the highest-risk piece and benefits from an isolated ship + monitor window before the API surface opens. Not required — 1.5d is still a single unit — but the dev agent may choose to land 1a separately in prod, verify migration integrity, then land 1b.

---

## Story cal-found-1: Calendar model, calendar_users join, backfill migration, CRUD endpoints

As Leo, I want the backend to know about calendars and have every existing meal safely parented under "My Calendar" so that any Flutter-side calendar work has something to talk to and no existing meal is orphaned.

### Acceptance Criteria

1. New SQLAlchemy models exist at `libraries/utils/utils/models/calendar.py` and `calendar_user.py` with columns per the architecture addendum. Both are registered in `libraries/utils/utils/models/__init__.py`.
2. `meal_events.calendar_id` and `meal_recurrence_rules.calendar_id` are added as nullable UUID FKs in the same alembic migration, with indexes on `(calendar_id, scheduled_at)` and `(calendar_id)` respectively.
3. The migration's backfill step creates exactly one calendar per existing `users` row with `name='My Calendar'`, `is_default=true`, `owner_id=user.id`, and one `calendar_users` row with `role='owner'`.
4. All existing `meal_events` and `meal_recurrence_rules` are backfilled with `calendar_id = (the owner's default calendar id)` in the same migration.
5. After backfill, the migration tightens both FKs to `NOT NULL`. Pre-tightening integrity check aborts the migration if any row remains NULL (test covers this via a synthetic NULL-row case).
6. Re-running the migration is a no-op: default calendar inserts use `ON CONFLICT DO NOTHING` keyed on a unique `(owner_id) WHERE is_default = true` partial index; backfill updates only rows where `calendar_id IS NULL`.
7. The down-migration drops both `calendar_id` FKs and the two new tables, without touching any meal_event/rule data.
8. `POST /api/v1/calendars` accepts `{name, description?}` and creates a calendar owned by the authenticated user, plus an `owner`-role `calendar_users` row atomically. Response: full calendar shape including `member_count = 1`.
9. `GET /api/v1/calendars` lists every calendar the authenticated user is a member of (owner or editor, though editor is only achievable via the sharing epic), grouped implicitly by ownership in the response (`owned: [...]` + `shared: [...]`). Ordered by `is_default DESC, created_at DESC`.
10. `GET /api/v1/calendars/{id}` returns the calendar + `members` list (id, user_id, role, invited_by_id, created_at). 404 if the user isn't a member.
11. `PATCH /api/v1/calendars/{id}` accepts `{name?, description?}`. Owner-only; non-owner members get 403.
12. `DELETE /api/v1/calendars/{id}` sets `archived_at = now()` on the calendar AND all its meal_events + recurrence rules (transactional). Owner-only. Idempotent: deleting an already-archived calendar returns 200 no-op. **Forbids** deleting the user's only calendar — returns `CALENDAR_CANNOT_DELETE_LAST` (new error code in 26x range) with HTTP 400. Writes an audit-log entry to `error_logs` with `service="audit"`.
13. User-provisioning flow is updated so a freshly-created `users` row atomically gets a default calendar. The hook is **itself idempotent**: creating a default calendar for a user that already has one is a no-op (not a 500), guarded by the partial unique index. This matters because Auth0 token refresh can replay the first-seen path. Test: signing up a brand-new user (integration test via Auth0-mocked path) results in exactly one default calendar; replaying the provisioning call is a no-op.
14. Migration creates a partial unique index `UNIQUE (owner_id) WHERE is_default = true AND archived_at IS NULL` — makes the "exactly one default per user" invariant DB-enforced, not handler-level.
15. Migration logs each step's row counts (users → calendars seeded, meal_events → backfilled, recurrence_rules → backfilled) to `error_logs` with `service="migrator"` so a prod run is observable.
16. The NOT-NULL tightening happens in the **same alembic revision** as the table creation + backfill. There is no intermediate ship where `calendar_id` is nullable in prod — the migration either lands fully or rolls back fully.
17. **Member-management handler stubs are NOT included in this story** — list/update/remove-member endpoints are owned by `epic-calendars-sharing` and shipped there. This story ships only `create`, `get`, `list`, `update`, `delete`.
18. `list_calendars` response is a flat list (not grouped) in this epic — every visible calendar is owned by the caller. The sharing epic adds the `owned` / `shared` grouping when editor-access becomes possible.
19. Tests in `services/api/tests/test_calendar_router.py` cover: create, get, list, update, delete-happy-path, delete-last-calendar-forbidden, delete-idempotent, non-member-404, non-owner-update-403, default-calendar-invariant (cannot create a second default directly; migration-enforced), user-provisioning-idempotent (double-call no-op), integration test for backfill (runs migration on a test DB with N users + M events + K rules, asserts every row has calendar_id + row counts logged), down-migration reversibility.

### Key Files
- Create: `libraries/utils/utils/models/calendar.py`, `calendar_user.py`
- Modify: `libraries/utils/utils/models/meal_event.py`, `meal_recurrence_rule.py`, `__init__.py`
- Create: `services/migrator/migrations/versions/<YYYYMMDDhhmmss>_add_calendars.py`
- Create: `services/api/src/api/v1/calendar/__init__.py`, `create_calendar.py`, `get_calendar.py`, `list_calendars.py`, `update_calendar.py`, `delete_calendar.py`
- Create: `services/api/src/routers/v1/calendar_router.py`, `services/api/src/schemas/calendar.py`
- Create: `services/api/tests/test_calendar_router.py`
- Modify: `services/api/src/main.py` (or wherever routers register) + the user-provisioning path

---

## Story cal-found-2: Rewire meal_event + recurrence rule authorization, require calendar_id, union shopping-list populate

As Leo, I want every calendar-related read and write to enforce calendar-membership authorization and refuse to create anything without a calendar_id so that calendars are the real unit of isolation — not just a label.

### Acceptance Criteria

1. A new FastAPI dependency `require_calendar_access(calendar_id, roles={'owner','editor'})` lives in `services/api/src/api/v1/calendar/dependencies.py`. Every meal_event + recurrence_rule handler consumes it; inline `SELECT FROM calendar_users` is forbidden. This is the auth primitive for every calendar-scoped resource going forward.
2. `POST /api/v1/meal-events` requires `calendar_id` in the request body (400 with specific error code `MEAL_EVENT_CALENDAR_REQUIRED`, not generic 422, if missing). The user must be owner or editor on that calendar (403 via `require_calendar_access`).
3. `POST /api/v1/recurrence-rules` requires `calendar_id` in the request body (400 with specific error code `RECURRENCE_RULE_CALENDAR_REQUIRED` if missing). Same auth rule via `require_calendar_access`.
4. `GET /api/v1/meal-events` accepts an optional `calendar_id` query param. When set, scopes to that calendar (403 if user isn't a member). When unset, scopes to all calendars the user is a member of (union).
5. `GET /api/v1/recurrence-rules` accepts the same optional `calendar_id` query param with the same semantics.
6. `GET /api/v1/meal-events/{id}`, `PATCH /api/v1/meal-events/{id}`, `DELETE /api/v1/meal-events/{id}`: all flow through `require_calendar_access`. Non-member → **404** on GET/DELETE (prevents resource-existence leaks), **403** on PATCH. Host/cohost/guest `meal_event_participants` are NOT consulted for edit authorization — regression test verifies a guest-participant who is NOT a calendar member gets 404 on GET (this is the real semantic-narrowing nailer; previously this path returned 200).
7. `PATCH /api/v1/meal-events/{id}` supports a new `calendar_id` field for Move-to-calendar. When set to a different calendar than the current one, validates the user is editor on BOTH source and destination calendars before committing. Same-calendar move (source == destination) is a validated no-op (returns 200 with no DB write, not a 500 from a redundant UPDATE). Transactional — partial move is not possible.
8. `PATCH /api/v1/recurrence-rules/{id}` supports the same `calendar_id` move semantics. Moving a rule updates `calendar_id` on the rule AND on all its existing materialized future `meal_events` (WHERE `scheduled_at >= now()`) in a single transaction. Past materialized rows are left unchanged.
9. `POST /api/v1/shopping-lists/{id}/populate-from-calendar-range` is updated to query meal_events across every calendar the user is a member of (owner + editor) in the date range. Existing request/response shape unchanged, including pagination and ordering — regression test via the existing shopping-list fixture confirms byte-equivalent output for single-calendar users.
10. Per-request N+1 guard: list endpoints fetch the user's `calendar_users` membership rows once per request and pass them down as an in-memory set; no per-row DB lookup.
11. Existing tests updated. New tests: guest-participant-who-is-NOT-a-calendar-member → 404 on GET (regression — this is the real test), move-meal-to-calendar-without-editor-on-destination-403, move-same-calendar-is-noop, move-rule-cascades-to-future-materialized-events-only, shopping-list-populate-unions-across-calendars, shopping-list-populate-single-calendar-user-byte-equivalent (ordering + pagination regression).

### Key Files
- Modify: every file in `services/api/src/api/v1/meal_event/` (create, get, list, update, delete, invite_participant, respond_to_invite, skip)
- Modify: every file in `services/api/src/api/v1/recurrence_rule/` (create, get, list, update, delete)
- Modify: `services/api/src/api/v1/shopping_list/populate_from_calendar_range.py`
- Modify: `services/api/src/schemas/meal_event.py`, `services/api/src/schemas/recurrence_rule.py` (add `calendar_id` to all request + response shapes)
- Modify: existing `services/api/tests/test_meal_event_router.py`, `test_recurrence_rule_router.py`, `test_shopping_list_router.py`
- Create: `services/api/tests/test_calendar_authorization.py` — covers the auth-rewire regressions

---

## Story cal-found-3: Flutter calendar switcher (header + bottom sheet + active-calendar provider + persistence)

As Leo, I want a header picker on the Calendar tab so I can see which calendar I'm looking at and swap between them in two taps.

### Acceptance Criteria

1. `calendar_screen.dart`'s top bar is replaced by `CalendarSwitcherHeader` — a compact chip/pill showing the active calendar's name with a chevron-down glyph. Tappable across its full width.
2. Tapping opens `CalendarSwitcherSheet` — a bottom sheet with:
   - Header "Calendars".
   - A list of calendar rows (name, subtitle "Owned by you" — no "0 others" noise). A checkmark or subtle highlight on the active row. The row body and trailing chevron are distinct hit targets (≥40px separation): tapping the row body activates the calendar; tapping the chevron opens Calendar Settings (story cal-found-4).
   - A "Shared with Me" section is present in code but `Visibility(visible: false)` in this epic — the sharing epic flips it on. Do NOT render an empty "Shared with Me" section with "nothing here yet" copy on day one.
   - A footer action **+ New Calendar** (story cal-found-4).
3. Selecting a calendar row sets the `activeCalendarProvider` state and dismisses the sheet; the calendar screen reloads meals scoped to the new calendar id.
4. **Scope of Riverpod use**: introduce `activeCalendarProvider` (Riverpod NotifierProvider) for the active-calendar state ONLY. The rest of the calendar feature (grid data loading via `_loadEvents`, etc.) stays `StatefulWidget` + plain services in this epic — do NOT incrementally migrate the whole feature to Riverpod here. The grid reads the active id from the provider at `initState` and on `didChangeDependencies`, then uses existing service calls.
5. `activeCalendarProvider` exposes two operations: `setActive(calendarId)` and `clearInvalid()` (used when the server returns 404 on the active id, e.g., the calendar was deleted from another device). Persists to `shared_preferences` on every change. On app start, hydrates from storage; if the stored id is unknown, falls back to the user's default calendar (first `is_default=true` in the list).
6. If `listCalendars` returns zero calendars (impossible post-backfill, but defensive), the provider surfaces an error state "Calendars unavailable, retry" rather than inventing client-side default. QA edge case nailed down.
7. All existing meal-loading code paths in the Calendar tab (`_loadEvents`, etc.) read the active calendar id from the provider and pass it as the `calendar_id` query param to the API.
8. Empty-state copy on the calendar grid updates when the active calendar has zero meals: "No meals on [calendar name] yet. Tap + to plan one." — matches the existing empty-state vocabulary.
9. The switcher handles the one-calendar case (first-ever open, only "My Calendar") gracefully — still renders the header with name + chevron, still opens the sheet, which shows one row + "+ New Calendar" action. The "Shared with Me" section remains hidden.
10. **Extract `CalendarPickerSheet`** as a reusable widget — the switcher sheet's body is a thin wrapper around it. Story cal-found-5's plan-meal Calendar row picker reuses this exact widget with a different `onSelect` callback.
11. Widget tests: rendering with 1 / 3 / 10 calendars; distinct-hit-target separation (tapping row body vs. chevron fires different actions); switching between them; persistence across app restarts (via a mocked `SharedPreferences`); fallback to default when stored id is invalid; `clearInvalid` path on server-404.

### Key Files
- Create: `app/lib/features/calendar/providers/active_calendar_provider.dart`
- Create: `app/lib/features/calendar/models/calendar.dart`
- Create: `app/lib/features/calendar/services/calendar_service.dart`
- Create: `app/lib/features/calendar/widgets/calendar_switcher_header.dart`
- Create: `app/lib/features/calendar/widgets/calendar_switcher_sheet.dart`
- Modify: `app/lib/features/calendar/calendar_screen.dart`, `services/meal_calendar_service.dart`
- Tests: `app/test/features/calendar/calendar_switcher_test.dart`, `active_calendar_provider_test.dart`

---

## Story cal-found-4: Flutter create/rename/delete calendar + user-provisioning default

As Leo, I want to create a new calendar, rename one, and delete ones I no longer need — plus trust that every user gets a default calendar on sign-up — so I can actually use the multi-calendar UX.

### Acceptance Criteria

1. The switcher sheet's **+ New Calendar** row opens `CalendarCreateDialog` — a modal dialog with a name field (required, autofocus, 128-char max matching the backend) and an optional multi-line description field. Create button is disabled until name is non-empty.
2. Submitting the dialog calls `calendarService.createCalendar(name, description?)`. On success, **the new calendar becomes the active calendar** (per FR104), the switcher sheet dismisses, and the grid reloads scoped to the new calendar. On failure (network, validation), the dialog stays open with the error surfaced as a snackbar.
3. Tapping the chevron on any calendar row in the switcher sheet opens `CalendarSettingsSheet` — a bottom sheet with:
   - A name field with an **explicit Save button** (not autosave-on-blur — matches recipe-book settings precedent; avoids debounce state machines and PATCH-per-keystroke churn).
   - A description field (same Save-button treatment).
   - A "Members" section that shows the **owner row** (the user themselves, role "Owner") with helper text "Sharing coming soon" below it. Not an empty section, not a disabled placeholder — one real row with a clear forward-looking label. The sharing epic adds more rows + a Share button; the structure is scaffolded now.
   - A destructive **Delete calendar** button at the bottom.
4. Renaming calls `updateCalendar(id, {name})` on Save. Failure: inline error, stays editable. Save button disables during in-flight.
5. Delete prompts a confirmation dialog whose copy varies by members count: "Delete '[name]'? All meals on this calendar will be archived. This cannot be undone." (solo). Scaffolded variant "Delete '[name]'? N members will lose access. All meals will be archived." is activated once members > 1 — template the copy now so the sharing epic doesn't require a second review round. Cancel/Delete buttons. On Delete → `deleteCalendar(id)` → dismiss the settings sheet AND the switcher sheet AND fall back per AC #6, then reload the calendar grid.
6. **Fallback rule after delete**: if the deleted calendar was active, fall back to the user's **default** calendar. If the default was the deletion target (only possible when it's not the last calendar), fall back to the **most recently created** remaining calendar. Explicitly ordered so no race between the cache and server-provided list ambiguity surfaces.
7. If the user tries to delete their **only** calendar, the Delete button is disabled with helper text "You can't delete your only calendar."
8. Widget tests: create happy path (new calendar becomes active), create-validation (empty name), rename-explicit-save (not autosave), delete-last-calendar-forbidden, delete-propagates-to-active-calendar-fallback-to-default, delete-default-falls-back-to-most-recent.

### Key Files
- Create: `app/lib/features/calendar/widgets/calendar_create_dialog.dart`, `calendar_settings_sheet.dart`
- Modify: `app/lib/features/calendar/widgets/calendar_switcher_sheet.dart` (wire + New Calendar + row chevron → settings sheet)
- Modify: user-provisioning handler on the backend (see cal-found-1)
- Tests: `app/test/features/calendar/calendar_create_dialog_test.dart`, `calendar_settings_sheet_test.dart`

---

## Story cal-found-5: Plan-meal-sheet Calendar row + Move-to-calendar action

As Leo, I want the plan-meal sheet to default to my active calendar and let me change destination per-meal, and I want to move an existing meal from one calendar to another without recreating it, so that I don't get trapped into putting the wrong meal on the wrong calendar.

### Acceptance Criteria

1. `plan_meal_sheet.dart` renders a new **Calendar** row at the top of the form (above the existing Date row), styled identically to the Date and Meal Type rows (read-only-text-plus-chevron affordance, consistent with `epic-recurring-meals-foundation` principle #5). **When the user has only one writable calendar, this row is hidden entirely** — not shown-disabled. A row that says "You only have one calendar" is noise for 80% of solo users on day one. Only surfaces when the user has N ≥ 2 writable calendars.
2. The row shows the active calendar's name by default. The form holds its own `_targetCalendarId` state, seeded from `activeCalendarProvider.read()` at sheet open. Changing the row mutates form state only — it never calls `setActive` on the provider. (Principle #5.)
3. Tapping opens `CalendarPickerSheet` (the reusable widget extracted in cal-found-3) listing only calendars the user can write to (owner or editor; in this epic, only owned).
4. On save, `createMealEvent` / `createRecurrenceRule` uses the form-state `_targetCalendarId`, not necessarily the active one.
5. For **Edit** mode (existing meal → plan-meal sheet via reschedule flow), the Calendar row shows the meal's current calendar. Changing it updates the meal's calendar on save (via the Move-to-calendar path in cal-found-2).
6. `meal_detail_sheet.dart` gains a **Move to calendar** action row in the secondary actions area (below the primary actions). **Hidden entirely when user has only one writable calendar** (matches principle #11). Tapping opens the same `CalendarPickerSheet`.
7. Move on a **one-off meal**: select in the picker → confirmation dialog "Move 'Dinner' to '[destination]'?" → `updateMealEvent(id, {calendarId: newId})` → dismiss sheets → grid reloads with the current `activeCalendarProvider` (if the meal moved away from the active calendar, it disappears from view).
8. Move on a **recurring occurrence**: rule-level action (not per-occurrence detach). Confirmation: "Move 'Pizza every Friday' to '[destination]'? This moves the whole series." On confirm → `PATCH /recurrence-rules/{ruleId}` with new `calendar_id` → backend cascades `calendar_id` update to future materialized meal_events → sheet closes (no stale summary line remains open) → grid reloads. Existing detach-on-edit semantics from `epic-recurring-meals-foundation` do not apply here — move is a rule-level change, not a per-occurrence edit.
9. Snackbar copy on success: "Moved to '[destination name]'." No undo (destructive bulk policy — matches End-series-today).
10. Widget tests: plan-meal default-to-active, plan-meal override-target-doesn't-mutate-provider, plan-meal-row-hidden-with-one-calendar, move-single-meal-confirms, move-recurring-meal-prompts-rule-level, move-row-hidden-with-one-calendar, plan-meal-edit-mode-preselects-meals-current-calendar.

### Key Files
- Modify: `app/lib/features/calendar/widgets/plan_meal_sheet.dart`, `meal_detail_sheet.dart`
- Create (or reuse from cal-found-3): the calendar picker bottom sheet — probably factor out the switcher-sheet body into a reusable `CalendarPickerSheet` widget, with the switcher wrapping it
- Modify: `app/lib/features/calendar/services/meal_calendar_service.dart` (calendar_id on every write)
- Tests: `app/test/features/calendar/plan_meal_sheet_calendar_picker_test.dart`, `meal_detail_sheet_move_test.dart`

---

## Dependencies

- **Upstream**: none. This epic is self-contained and ships independently.
- **Downstream**: `epic-calendars-sharing` strictly depends on this — its invitation-system extension assumes `calendars` + `calendar_users` tables exist and the calendar resource authorization is already in place.
- **Cross-epic**: `epic-recurring-meals-editing` (currently in-flight / done) operates on `meal_recurrence_rules` — cal-found-2 adds the `calendar_id` column and the auth rewrite. The editing-epic's existing handlers get the calendar-scoped auth treatment as part of cal-found-2 (no coordination needed beyond the rewrite landing cleanly).

## Locked Cross-Epic Decisions (propagate to calendars-sharing)

- **Editors cannot invite others.** Only owners can add/remove members. Sharing epic's `check_resource_permission` branch for `resource_type='calendar'` must enforce owner-only on member-mutating endpoints.
- **`CALENDAR_CANNOT_DELETE_LAST`** (26x range) is the new error code for delete-last-calendar. Sharing epic's leave-calendar flow reuses the "cannot leave if last owner" semantics with a parallel code (`CALENDAR_OWNER_CANNOT_LEAVE`).
- **Host/cohost/guest no longer grants edit authorization.** Permanent semantic narrowing verified via the foundation regression test. Sharing-epic docs must call this out whenever per-meal invites are discussed.
- **Audit log on calendar mutations** (delete, ownership transfer, member add/remove) uses `service="audit"`. Sharing epic inherits this pattern for the member endpoints it adds.
- **`require_calendar_access` FastAPI dependency** is the one-and-only auth primitive for calendar-scoped resources. Sharing epic's new endpoints use it — do not reinvent.
- **`CalendarPickerSheet` widget** is shared infra (extracted in cal-found-3). Sharing epic's "invite to calendar" flow that picks which calendar to share reuses it as the picker source.
- **Flutter active-calendar state is Riverpod** (`activeCalendarProvider`). Sharing-epic UI (accept invite → land on new calendar) sets `setActive(newCalendarId)` on accept.
- **No viewer role, ever.** Sharing epic's role enum is locked at `{owner, editor}`. Defer any future viewer conversation to its own proposal.
- **Partial unique index `UNIQUE (owner_id) WHERE is_default = true AND archived_at IS NULL`** is the DB-enforced invariant for "exactly one default per user." Sharing epic must not introduce any code path that flips `is_default` across calendar_users rows or violates the invariant (e.g., ownership transfer does NOT change `is_default` on the calendar — it stays where it was).

## Definition of Done (Epic Level)

- Backfill migration lands in prod; every existing user has exactly one default calendar; every existing `meal_event` and `meal_recurrence_rule` has a non-null `calendar_id`.
- Calendar tab header shows the active calendar name with a tappable chevron; switcher bottom sheet lists owned calendars (+ empty "Shared with Me" scaffold); users can create, rename, and delete calendars.
- `calendar_id` is required on all meal_event + recurrence-rule writes; authorization on all reads/writes consults `calendar_users`; host/cohost/guest roles no longer grant edit authorization (regression tested).
- Move-to-calendar works from the meal detail sheet (single meal) and carries the whole rule for recurring meals.
- Shopping-list `PopulateFromCalendarRange` unions across all user-accessible calendars.
- New users sign up → immediately own a default calendar named "My Calendar".
- Down-migration is verified reversible.
- All P0 tests pass in CI.

## Open Questions — Resolved 2026-04-17

All party-mode-surfaced questions locked by the user:

- ✅ **Move-to-calendar on recurring occurrence**: rule-level (principle #7, cal-found-5 AC #8).
- ✅ **`auto_populate_from_calendar` per-list scoping**: union across all accessible calendars (PRD FR113 Out-of-Scope).
- ✅ **Post-migration client rollout**: ship atomically. No two-phase. Stale iOS clients writing without `calendar_id` get 400 until they update. Principle #12 stands. *User: "ship it, no users on the platform yet."*
- ✅ **Default calendar rename**: allowed. `is_default` is independent of name. User may rename "My Calendar" to anything.
- ✅ **Household-shared recurrence rules post-calendars**: calendar membership is the **sole gate**. Household-shared rules are grandfathered via their default-calendar backfill, but going forward, only `calendar_users` membership grants CRUD. Principle #1 holds.
- ✅ **Legacy `is_recurring` / `recurrence_rule` / `recurrence_end_date` / `parent_event_id` cleanup**: **at the end**. Deferred until after this epic + calendars-sharing ship and stabilize. Dev agent must NOT touch these columns during the backfill migration; they remain dead weight.
- ✅ **Calendar Settings rename**: explicit Save button (principle #14, cal-found-4 AC #3).
