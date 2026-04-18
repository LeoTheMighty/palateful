# Story cal-found-1.1: Calendar model, calendar_users join, backfill migration, CRUD endpoints

Status: ready-for-dev

## Story

As Leo,
I want the backend to know about calendars and have every existing meal safely parented under "My Calendar",
so that any Flutter-side calendar work has something to talk to and no existing meal is orphaned.

## Acceptance Criteria

1. **New SQLAlchemy models** exist at `libraries/utils/utils/models/calendar.py` and `calendar_user.py` per the architecture addendum. Both registered in `libraries/utils/utils/models/__init__.py`. `Calendar` inherits `Base` (id + timestamps + archived_at); `CalendarUser` inherits `JoinsBase` (no id, composite PK `(calendar_id, user_id)`).
2. **`meal_events.calendar_id` and `meal_recurrence_rules.calendar_id`** added as nullable UUID FKs in the same alembic migration, with `ON DELETE RESTRICT`. Indexes: `(calendar_id, scheduled_at)` on `meal_events` and `(calendar_id)` on `meal_recurrence_rules`.
3. **Backfill** creates exactly one calendar per existing `users` row with `name='My Calendar'`, `is_default=true`, `owner_id=user.id`, plus one `calendar_users` row with `role='owner'` per user.
4. All existing `meal_events` and `meal_recurrence_rules` are backfilled with `calendar_id = (the owner's default calendar id)` in the same migration.
5. After backfill, the migration tightens both FKs to `NOT NULL`. Pre-tightening integrity check aborts the migration if any row remains NULL. Synthetic NULL-row test case covers this.
6. Re-running the migration is a no-op: default calendar inserts use `ON CONFLICT DO NOTHING` keyed on a partial unique index `UNIQUE (owner_id) WHERE is_default = true AND archived_at IS NULL`; backfill updates only rows where `calendar_id IS NULL`.
7. Down-migration drops both `calendar_id` FKs and the two new tables, without touching any meal_event/rule data. `meal_events` / `meal_recurrence_rules` retain their owner_id scoping as before.
8. `POST /api/v1/calendars` accepts `{name, description?}` and atomically creates (a) a calendar owned by the authenticated user and (b) an `owner`-role `calendar_users` row. Response: full calendar shape including `member_count = 1`.
9. `GET /api/v1/calendars` returns a **flat list** of every calendar the authenticated user is an active (`archived_at IS NULL`) member of. Ordered by `is_default DESC, created_at DESC`. (No `owned`/`shared` grouping in this epic — sharing epic adds it when editor-access becomes possible.)
10. `GET /api/v1/calendars/{id}` returns the calendar + `members` list (user_id, name, role, invited_by_id, created_at). **404** if the user isn't an active member (no existence-leak).
11. `PATCH /api/v1/calendars/{id}` accepts `{name?, description?}`. Owner-only; non-owner members get **403**. Members-mutating endpoints are NOT in this story.
12. `DELETE /api/v1/calendars/{id}` sets `archived_at = now()` on the calendar AND cascades to its meal_events AND meal_recurrence_rules (all in one transaction). Owner-only; non-owner members get **403**. Idempotent: deleting an already-archived calendar returns 200 no-op. **Forbids** deleting the user's only active calendar — returns HTTP 400 with new error code `CALENDAR_CANNOT_DELETE_LAST = 261`. Writes an audit row to `error_logs` with `service="audit"`, `error_type="CalendarArchiveAudit"`.
13. User-provisioning flow is updated so a freshly-created `users` row atomically gets a default calendar. Hook lives in `services/api/src/dependencies.py` alongside the existing `find_or_create_by(User, ...)` block. **Idempotent**: re-entering the provisioning path for an existing user with an existing default is a silent no-op (partial unique index catches the race). Test: signing up a brand-new user gets exactly one default calendar; replaying the provisioning call is a no-op.
14. Migration creates the partial unique index `UNIQUE (owner_id) WHERE is_default = true AND archived_at IS NULL` on `calendars`. DB-enforced "exactly one default per user" invariant.
15. Migration logs row counts at each step (users seeded, meal_events backfilled, recurrence_rules backfilled) to `error_logs` with `service="migrator"`, `error_type="CalendarBackfillStep"` so a prod run is observable.
16. NOT-NULL tightening happens in the **same alembic revision** as the table creation + backfill. No intermediate ship where `calendar_id` is nullable in prod.
17. Member-management handler stubs are **NOT** in this story (owned by `epic-calendars-sharing`). This story ships only `create`, `get`, `list`, `update`, `delete`.
18. Tests in `services/api/tests/test_calendar_router.py` cover: create, get, list, update, delete-happy-path, delete-last-calendar-forbidden (→ 400 with `CALENDAR_CANNOT_DELETE_LAST`), delete-idempotent, non-member-404, non-owner-update-403, non-owner-delete-403, user-provisioning-idempotent. Existing meal_event and recurrence_rule tests must continue to pass (calendar_id column is nullable at the SQLAlchemy level until cal-found-2 requires it).

## Tasks / Subtasks

- [ ] **Task 1 — SQLAlchemy models** (AC: 1)
  - [ ] Create `libraries/utils/utils/models/calendar.py` with `Calendar(Base)`: columns `name: str(128)`, `description: str|None`, `is_shared: bool default=false`, `is_default: bool default=false`, `color: str(7)|None`, `owner_id: UUID FK users ondelete=CASCADE`. Relationships: `members: list["CalendarUser"]` (back_populates, cascade all delete-orphan), `owner: User` (foreign_keys=[owner_id]).
  - [ ] Create `libraries/utils/utils/models/calendar_user.py` with `CalendarUser(JoinsBase)`: composite PK `(calendar_id, user_id)` both UUID FKs ondelete=CASCADE, `role: str(16)` default=`"editor"` (CHECK constraint in migration: `role IN ('owner','editor')`), `invited_by_id: UUID|None FK users ondelete=SET NULL`, `last_opened_at: datetime|None`. Relationships: `calendar: Calendar` (back_populates="members"), `user: User` (foreign_keys=[user_id]).
  - [ ] Register both in `libraries/utils/utils/models/__init__.py` (import + `__all__`).
  - [ ] Add `calendar_id: UUID|None FK calendars ondelete=RESTRICT` to `meal_event.py` and `meal_recurrence_rule.py`. **SQLAlchemy-level `nullable=True`** for now (migration tightens it). Update `__table_args__` to include new indexes: on `meal_events`, `Index("ix_meal_events_calendar_id_scheduled_at", "calendar_id", "scheduled_at")`; on `meal_recurrence_rules`, `Index("ix_meal_recurrence_rules_calendar_id", "calendar_id")`.

- [ ] **Task 2 — Alembic migration** (AC: 2, 3, 4, 5, 6, 7, 14, 15, 16)
  - [ ] Create `services/migrator/migrations/versions/20260417000002_add_calendars.py` with `down_revision = "a1r2e3c4u5r6"` (the meal_recurrence_rules migration).
  - [ ] Step 1 — Create `calendars` table (with Base columns: id UUID PK default=`gen_random_uuid()`, created_at/updated_at/archived_at) + `calendar_users` table (composite PK, no id, all timestamps + archived_at). Include CHECK constraint on `calendar_users.role IN ('owner', 'editor')`. Add indexes: `(owner_id)` on calendars; partial unique `UNIQUE (owner_id) WHERE is_default = true AND archived_at IS NULL` on calendars; `(user_id, archived_at)` and `(calendar_id)` on calendar_users.
  - [ ] Step 2 — `op.add_column("meal_events", sa.Column("calendar_id", UUID, nullable=True, ...))` + index `ix_meal_events_calendar_id_scheduled_at`. Same for `meal_recurrence_rules`.
  - [ ] Step 3 — Backfill calendars: `INSERT INTO calendars (id, owner_id, name, is_default, ...) SELECT gen_random_uuid(), id, 'My Calendar', true, ... FROM users ON CONFLICT (owner_id) WHERE is_default = true AND archived_at IS NULL DO NOTHING`. Then `INSERT INTO calendar_users (calendar_id, user_id, role, ...) SELECT c.id, c.owner_id, 'owner', ... FROM calendars c LEFT JOIN calendar_users cu ON cu.calendar_id = c.id AND cu.user_id = c.owner_id WHERE cu.user_id IS NULL`. Log row counts to `error_logs`.
  - [ ] Step 4 — Backfill FKs: `UPDATE meal_events SET calendar_id = (SELECT id FROM calendars WHERE owner_id = meal_events.owner_id AND is_default = true AND archived_at IS NULL) WHERE calendar_id IS NULL`. Same for `meal_recurrence_rules`. Log row counts.
  - [ ] Step 5 — Integrity check: `SELECT COUNT(*) FROM meal_events WHERE calendar_id IS NULL` — if > 0, raise `RuntimeError("Backfill incomplete: N meal_events have NULL calendar_id")`. Same for `meal_recurrence_rules`.
  - [ ] Step 6 — `op.alter_column("meal_events", "calendar_id", nullable=False)`. Same for `meal_recurrence_rules`.
  - [ ] Downgrade: drop indexes on meal_events/meal_recurrence_rules, drop calendar_id column on both, drop calendar_users then calendars. Leaves meal data untouched (still owner_id scoped).
  - [ ] Helper function `_log_migrator_step(conn, step_name, counts_dict)` inserts to `error_logs` with `service="migrator"`, `error_type="CalendarBackfillStep"`.

- [ ] **Task 3 — Pydantic schemas** (AC: 8, 9, 10, 11)
  - [ ] Create `services/api/src/schemas/calendar.py` with: `CalendarCreateRequest(name, description?)`, `CalendarUpdateRequest(name?, description?)`, `CalendarResponse(id, name, description, is_default, is_shared, owner_id, member_count, user_role, created_at, updated_at)`, `CalendarMemberResponse(user_id, name, role, invited_by_id, created_at)`, `CalendarDetailResponse(CalendarResponse + members: list[CalendarMemberResponse])`, `CalendarListResponse(items: list[CalendarResponse])`. (No pagination — users will rarely have >20 calendars; a flat list is fine.)

- [ ] **Task 4 — CRUD endpoint handlers** (AC: 8, 9, 10, 11, 12)
  - [ ] Create `services/api/src/api/v1/calendar/` with `__init__.py` re-exporting all endpoint classes.
  - [ ] `create_calendar.py` — `CreateCalendar(Endpoint)`. Creates Calendar + CalendarUser(role=owner) atomically. Returns 201 + `CalendarResponse` with `member_count=1`, `user_role="owner"`.
  - [ ] `get_calendar.py` — `GetCalendar(Endpoint)`. Looks up `CalendarUser(user_id=user.id, calendar_id=calendar_id, archived_at IS NULL)`. If missing → **404** `CALENDAR_NOT_FOUND = 262`. Update `last_opened_at = now()`. Fetch all active members. Return `CalendarDetailResponse`.
  - [ ] `list_calendars.py` — `ListCalendars(Endpoint)`. Joins Calendar↔CalendarUser on user_id=user.id, filters `calendar.archived_at IS NULL AND cu.archived_at IS NULL`. Subquery for member_count. Order `is_default DESC, created_at DESC`. Returns `CalendarListResponse`.
  - [ ] `update_calendar.py` — `UpdateCalendar(Endpoint)`. Resolve membership; if not owner → 403 `CALENDAR_ACCESS_DENIED = 263`. Apply `{name, description}` updates. Returns `CalendarResponse`.
  - [ ] `delete_calendar.py` — `DeleteCalendar(Endpoint)`. Resolve membership; owner-only or 403. Idempotency guard: if `calendar.archived_at is not None` → return 200 no-op. **Count active owned calendars for user**: `SELECT COUNT(*) FROM calendars c JOIN calendar_users cu ON cu.calendar_id=c.id WHERE cu.user_id=:me AND cu.role='owner' AND c.archived_at IS NULL`. If == 1 (i.e. this is the last one) → 400 `CALENDAR_CANNOT_DELETE_LAST = 261`. Otherwise: in a single transaction, set `archived_at=now()` on calendar, all its meal_events, all its meal_recurrence_rules, and all calendar_users rows. Write audit row to error_logs.

- [ ] **Task 5 — Router + registration** (AC: 8–12)
  - [ ] Create `services/api/src/routers/v1/calendar_router.py` — prefix `/calendars`, tags `["calendars"]`. Routes: `GET ""`, `POST ""`, `GET /{calendar_id}`, `PATCH /{calendar_id}`, `DELETE /{calendar_id}`. Mirror the recipe_book_router structure.
  - [ ] Mount in `services/api/src/routers/v1_router.py` (wherever recipe_book_router is included). Follow alphabetical convention if used.

- [ ] **Task 6 — Error code extensions** (AC: 12)
  - [ ] Add to `libraries/utils/utils/classes/error_code.py` in the 26x range (after `TOKEN_CAP_EXCEEDED = 260`): `CALENDAR_CANNOT_DELETE_LAST = 261`, `CALENDAR_NOT_FOUND = 262`, `CALENDAR_ACCESS_DENIED = 263`. (Codes 264–269 reserved for cal-found-2: `MEAL_EVENT_CALENDAR_REQUIRED`, `RECURRENCE_RULE_CALENDAR_REQUIRED`, etc.)

- [ ] **Task 7 — User-provisioning hook** (AC: 13)
  - [ ] In `services/api/src/dependencies.py::get_current_user`, after `find_or_create_by(User, auth0_id=...)`, call a new helper `_ensure_default_calendar(database, user)` that: queries for an active default calendar owned by user; if missing, creates Calendar(name='My Calendar', is_default=True) + CalendarUser(role='owner') atomically. Wrap the insert in a try/except catching the partial-unique-index `IntegrityError` (IntegrityError on `is_default` partial index means a concurrent request already created one — swallow + retry lookup, no-op). Same code path used by e2e-test-user bypass above — ensure that branch also provisions a default calendar.

- [ ] **Task 8 — Audit-log helper** (AC: 12)
  - [ ] Use the existing `ErrorLog` model directly (same pattern as `promote_admin.py`). In `delete_calendar.py`, after archiving, insert `ErrorLog(service="audit", error_type="CalendarArchiveAudit", error_message=f"Calendar {calendar_id} archived by user {user.id}", user_id=user.id)` via `self.database.create(...)`.

- [ ] **Task 9 — Tests** (AC: 18)
  - [ ] Create `services/api/tests/test_calendar_router.py` following `test_recipe_book.py` patterns — use `mock_db` / `mock_user` fixtures + `MockCalendar` + `MockCalendarUser` helpers (add to `conftest.py`).
  - [ ] Cases: create (201 + response shape), get (200 + members), get-non-member (404), list (flat, ordered), update-owner (200), update-non-owner (403), delete-owner (200), delete-non-owner (403), delete-last-calendar (400 + CALENDAR_CANNOT_DELETE_LAST), delete-already-archived (200 no-op, no duplicate audit row), user-provisioning-on-auth-creates-default, user-provisioning-idempotent-no-dup.
  - [ ] Integration test stub: `services/api/tests/test_calendar_backfill_migration.py` — optional but preferred. Seeds N users + M meal_events + K recurrence_rules via raw SQL against a fresh SQLite DB, runs the upgrade function with a real `op.get_bind()`-compatible conn, asserts every event/rule has a calendar_id and row counts logged.

- [ ] **Task 10 — Lint + test + check-models** (local CI before commit)
  - [ ] `npx nx run api:lint` passes
  - [ ] `npx nx run migrator:lint` passes
  - [ ] `npx nx run utils:lint` passes (since models changed)
  - [ ] `npx nx run api:test` passes
  - [ ] `npx nx run migrator:check-models` passes (model-drift check against fresh-migrated test DB)

## Dev Notes

### Architecture compliance (MUST read [Source: _bmad-output/planning-artifacts/architecture.md#Addendum — 2026-04-17 — Calendar as First-Class Container])

- `Calendar` table mirrors `RecipeBook`; `CalendarUser` mirrors `RecipeBookUser`. Keep the column-order parallel where possible so future refactors (shared "container base class"?) are cheap.
- `role` is restricted to `{owner, editor}` — **no viewer role ever**. CHECK constraint must encode this. Sharing epic assumes this lock.
- Partial unique index is the **DB-enforced** invariant; handler-level guards are not sufficient. Concurrent default-calendar creation must race-abort via IntegrityError.
- FK `ON DELETE RESTRICT` on `meal_events.calendar_id` + `meal_recurrence_rules.calendar_id` is intentional: calendar archive is soft via `archived_at`, not hard delete. Hard-delete of a calendar with events should fail loudly (sentinel for a bug).
- This story does NOT extend the invitation system. `VALID_ROLES["calendar"]` registration is cal-share-1's job.

### File structure (Where things live)

```
libraries/utils/utils/models/
├── calendar.py                                  # NEW
├── calendar_user.py                             # NEW
├── meal_event.py                                # MODIFIED (+ calendar_id)
├── meal_recurrence_rule.py                      # MODIFIED (+ calendar_id)
└── __init__.py                                  # MODIFIED (register new models)

libraries/utils/utils/classes/
└── error_code.py                                # MODIFIED (+ 261–263)

services/migrator/migrations/versions/
└── 20260417000002_add_calendars.py              # NEW

services/api/src/api/v1/calendar/                # NEW
├── __init__.py
├── create_calendar.py
├── get_calendar.py
├── list_calendars.py
├── update_calendar.py
└── delete_calendar.py

services/api/src/schemas/
└── calendar.py                                  # NEW

services/api/src/routers/v1/
└── calendar_router.py                           # NEW

services/api/src/routers/
└── v1_router.py                                 # MODIFIED (include calendar_router)

services/api/src/
└── dependencies.py                              # MODIFIED (_ensure_default_calendar)

services/api/tests/
├── test_calendar_router.py                      # NEW
├── test_calendar_backfill_migration.py          # NEW (integration)
└── conftest.py                                  # MODIFIED (MockCalendar + MockCalendarUser)
```

### Reference patterns (copy-paste fuel)

- **Endpoint base class** → `libraries/utils/utils/api/endpoint.py` — `Endpoint.call(params, user, database)` → returns `{success, data, status}`. See `services/api/src/api/v1/recipe_book/create_recipe_book.py` for the minimal pattern.
- **Delete-with-cascade pattern** → `services/api/src/api/v1/recipe_book/delete_recipe_book.py` (owner-only check + auto-recovery). Our version adds the "last calendar" guard and cascades archived_at to meal_events + rules.
- **Migration backfill pattern** → `services/migrator/migrations/versions/20260416100000_backfill_default_shopping_list.py` — batched loop over users, INSERT + UPDATE per row. Our migration is a single SET-based UPDATE (no need for batching with <100 users).
- **Migration with new FK + index** → `services/migrator/migrations/versions/20260417000001_add_meal_recurrence_rules.py` — down_revision chain, `op.add_column`, `op.create_index` with partial-where, downgrade mirrors upgrade.
- **Audit log pattern** → `services/api/scripts/promote_admin.py::_write_audit_row` — writes to `error_logs` with `service="audit"`. We'll use the `ErrorLog` model via `self.database.create(...)` instead of raw SQL since we're inside the request flow.
- **User provisioning hook** → `services/api/src/dependencies.py::get_current_user` and `_finalize_auth`. Add `_ensure_default_calendar(database, user)` between `find_or_create_by(User, ...)` and `_finalize_auth(...)`. Make it tolerant to the e2e-test branch too.
- **Test conftest patterns** → `services/api/tests/conftest.py::MockRecipeBook`, `MockRecipeBookUser`. Add `MockCalendar` + `MockCalendarUser` following the same shape.

### Error codes (extend `libraries/utils/utils/classes/error_code.py`)

```
# AI Chat errors (260-269)  [existing]
TOKEN_CAP_EXCEEDED = 260

# Calendar errors (261-269)  [NEW in this story]
CALENDAR_CANNOT_DELETE_LAST = 261
CALENDAR_NOT_FOUND = 262
CALENDAR_ACCESS_DENIED = 263

# (264-269 reserved for cal-found-2: MEAL_EVENT_CALENDAR_REQUIRED,
#  RECURRENCE_RULE_CALENDAR_REQUIRED, etc.)
```

Note: The existing 26x-range comment in the enum lumps AI Chat (260) together; we're extending it for Calendar (261-269). Update the comment header to reflect both domains, or split into "AI Chat (260)" and "Calendar (261-269)".

### `user_role` on list/get responses (future-proofing for sharing epic)

Even though in this epic only owner-role is possible, include `user_role: str` on `CalendarResponse`. The sharing epic will populate `"editor"` for shared calendars without a schema change — avoids a response-shape bump later.

### Idempotency of user-provisioning hook (CRITICAL)

Auth0 token refresh replays `get_current_user` for existing users. The hook must:
1. Read current state first (cheap). If user already has an active default calendar → return immediately.
2. If missing, attempt insert. Catch `IntegrityError` on the partial unique index. Swallow + re-read. If re-read finds a calendar, return it. If still missing after retry, re-raise (something is actually broken).
3. Never raise to the caller in the "already-exists" case — provisioning must never break auth.

### Why `ON DELETE RESTRICT` and not `CASCADE`

Calendars are archived, not deleted. If a hard DELETE is ever issued (migration mistake, admin script typo), we want it to fail loudly instead of silently nuking events. `CASCADE` would bury the data-loss behavior; `RESTRICT` surfaces it.

### Test-env caveat for the user-provisioning hook

The e2e-test bypass (`_E2E_TOKEN`) in `dependencies.py` creates a test user on the fly. Applying `_ensure_default_calendar` to that branch means existing e2e tests now get a default calendar — should be transparent, but double-check `services/api/tests/test_dependencies.py` for any test that asserts zero calendars post-auth (unlikely, but cheap to check).

### Migration row-count logging (AC 15)

```python
def _log_migrator_step(conn, step_name, **counts):
    conn.execute(
        sa.text(
            """
            INSERT INTO error_logs
                (id, created_at, updated_at, error_type, error_message, service, user_id)
            VALUES
                (gen_random_uuid(), NOW(), NOW(),
                 'CalendarBackfillStep', :msg, 'migrator', NULL)
            """
        ),
        {"msg": f"{step_name}: {counts}"},
    )

# Usage:
_log_migrator_step(conn, "seed_calendars", users_seeded=n_users, calendars_created=n_inserted)
_log_migrator_step(conn, "backfill_meal_events", rows_updated=n_events)
_log_migrator_step(conn, "backfill_recurrence_rules", rows_updated=n_rules)
```

### Previous story intelligence

**From `rm-found-*` (recurring meals foundation, done)**: `meal_recurrence_rules` table shape; recurrence model lives at `libraries/utils/utils/models/meal_recurrence_rule.py`. Pattern of `materialized_through`-style data migrations worked fine without downtime — our migration is even simpler (no data rewriting, just backfill + tighten).

**From `bugs-imp-ing-5` (structured ingredients backend, done)**: Endpoint-schema pattern with nested `ResponseItem` BaseModels inside the endpoint class works. Prefer that shape for our Calendar handlers rather than hoisting everything into `schemas/calendar.py` — except shared shapes (`CalendarResponse`, `CalendarMemberResponse`) which the sharing epic will reuse, so they go in `schemas/calendar.py`.

**From `promote_admin.py`**: Audit row pattern is `INSERT INTO error_logs (..., service='audit', error_type='<AuditName>', ...)`. Using the `ErrorLog` SQLAlchemy model is preferable inside the request flow (auto timestamps, auto id); raw SQL is only for standalone ops scripts.

**From architecture addendum line 928**: "If non-zero, abort migration (data integrity check)" — this is explicit: the migration should raise a `RuntimeError` (not a generic `Exception`) so operators see a clear alembic failure message.

### Git intelligence (recent commit patterns)

- `feat(app): bugs-imp-ing-4 — StructuredIngredientRow in wizard + edit` — message format: `feat(<service>): <story-id> — <title>`. Use `feat(api): cal-found-1 — calendar model + backfill + CRUD` for our commit.
- `bb8999f chore(app): bump to 1.0.8+21 for structured ingredient editor` — pubspec bumps are separate commits with `chore(app)` prefix. This story doesn't touch Flutter, so no bump.

### QA Walkthrough Checklist

Output both in-story AND to `cal-found-1-qa-walkthrough.md` per memory feedback:

**Backend API smoke tests (after migration runs):**
- [ ] `GET /api/v1/calendars` as any existing user returns exactly one calendar with `name="My Calendar"`, `is_default=true`, `member_count=1`, `user_role="owner"`.
- [ ] `POST /api/v1/calendars` with `{name: "Meal Prep"}` returns 201 + new calendar. `GET /api/v1/calendars` now returns two calendars ordered `[My Calendar, Meal Prep]` (default first, then created_at DESC).
- [ ] `PATCH /api/v1/calendars/{meal-prep-id}` with `{name: "Prep"}` returns 200 + updated name.
- [ ] `DELETE /api/v1/calendars/{meal-prep-id}` returns 200, calendar archived. Querying `GET /api/v1/calendars` no longer returns it. Direct DB check: `archived_at IS NOT NULL` on the calendar and all its calendar_users rows.
- [ ] `DELETE /api/v1/calendars/{my-calendar-id}` (the last one) returns 400 with `{error: {code: 261}}`.
- [ ] As User B (non-member), `GET /api/v1/calendars/{user-a-calendar-id}` returns 404.

**Backend DB verification (post-migration):**
- [ ] `SELECT COUNT(*) FROM meal_events WHERE calendar_id IS NULL` → 0.
- [ ] `SELECT COUNT(*) FROM meal_recurrence_rules WHERE calendar_id IS NULL` → 0.
- [ ] `SELECT COUNT(*) FROM calendars WHERE is_default = true` == `SELECT COUNT(*) FROM users` (one default per user).
- [ ] `SELECT COUNT(*) FROM calendar_users WHERE role = 'owner'` == `SELECT COUNT(*) FROM calendars` (one owner per calendar).
- [ ] `SELECT * FROM error_logs WHERE service = 'migrator' AND error_type = 'CalendarBackfillStep' ORDER BY created_at` returns ≥3 rows (seed, backfill_events, backfill_rules).

**New-user provisioning:**
- [ ] Fresh Auth0 signup → user has exactly one default calendar. Call `get_current_user` again (simulate token refresh) → still one calendar.

**Down-migration reversibility (on a staging DB):**
- [ ] `alembic downgrade <prev>` drops calendars + calendar_users + calendar_id FKs. `meal_events` still queryable. `owner_id` scoping still works for older clients.

### Project Structure Notes

- All file paths match existing conventions (`libraries/utils/utils/models/<snake_case>.py`, `services/api/src/api/v1/<resource>/<verb_resource>.py`, etc.).
- No new top-level folders.
- No new services, queues, Terraform, or env vars. Per architecture addendum line 961: "No new AWS resources, no Terraform changes, no new queues."

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Addendum — 2026-04-17 — Calendar as First-Class Container (lines 895–965)]
- [Source: _bmad-output/planning-artifacts/epic-calendars-foundation.md#Story cal-found-1 (lines 172–206)]
- [Source: libraries/utils/utils/models/recipe_book.py — Calendar mirror]
- [Source: libraries/utils/utils/models/recipe_book_user.py — CalendarUser mirror]
- [Source: services/api/src/api/v1/recipe_book/ — CRUD handler patterns]
- [Source: services/migrator/migrations/versions/20260417000001_add_meal_recurrence_rules.py — FK + index migration pattern]
- [Source: services/migrator/migrations/versions/20260416100000_backfill_default_shopping_list.py — data backfill pattern]
- [Source: services/api/scripts/promote_admin.py — audit row pattern]
- [Source: libraries/utils/utils/classes/error_code.py — error code enum]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

### Completion Notes List

### File List
