# Story abi-1: Backend — `unread-count` structured payload + allow-list

Status: ready-for-dev

## Story

As the Activity backend,
I want the unread-count endpoint to return separate counts for notifications and actionable imports, filtered by a single source-of-truth allow-list for notification types,
so that the frontend badge formula is a pure sum of two fields that exactly match what the two tab bodies render.

## Acceptance Criteria

1. `NOTIFICATION_TAB_TYPES` module-level constant in `libraries/utils/utils/models/user_activity.py`: a `frozenset[str]` or `tuple[str, ...]` exported at module top-level. Current membership: `('partner_action',)`. Adding a value here is the only way to make a `user_activity.type` visible in the Notifications tab or the bell.
2. `GET /v1/activities/unread-count` returns `{notifications: int, imports_actionable: int, count: int}`. `count = notifications + imports_actionable` (backward-compat wrapper, deprecated in docstring).
3. `notifications` count query: `user_id = me AND read = false AND archived_at IS NULL AND type IN NOTIFICATION_TAB_TYPES AND created_at >= NOW() - INTERVAL '30 days'`. Mirrors the `list_activities` window exactly.
4. `imports_actionable` count query: over `import_items` joined to `import_jobs` (for `user_id`) — `jobs.user_id = me AND items.archived_at IS NULL AND items.dismissed_at IS NULL AND items.status IN ('pending','processing','extracting','matching','awaiting_parser','awaiting_review','failed')`. Green (`status='completed' AND created_recipe_id IS NOT NULL`) excluded by virtue of not being in the status set.
5. `GET /v1/activities` (`list_activities.py`) filters by `type IN NOTIFICATION_TAB_TYPES` by default. New optional query param `?include_system_types=true` restores old behavior.
6. Unit tests for `unread_count`: seed 3 partner_action (unread) + 1 invitation (unread, not in allow-list) + 2 needs-review import_items + 1 completed+created_recipe_id import_item. Expect `{notifications: 3, imports_actionable: 2, count: 5}`.
7. Backward-compat test: `count` == `notifications + imports_actionable`. Module-level deprecation comment on the `count` field notes "remove after epic-activity-full-history ships".
8. `list_activities` combined filter test: seed archived partner_action (should NOT return) + unarchived import_started (should NOT return by default) + unarchived partner_action (SHOULD return). Default request returns 1 row; `?include_system_types=true` (admin) returns 2.
9. `?include_system_types=true` admin-gate: a non-admin calling with the flag gets 403 `detail="Admin access required"` (reuses `require_admin` semantics). Non-admin without flag gets the default-filtered list.
10. The two count queries execute sequentially on one DB session (per endpoint docstring). No `asyncio.gather`.
11. Coverage stays at 100% on `services/api/src/api/v1/user_activity/` (enforced by CI).
12. Index plan: the `notifications` count query uses `ix_user_activities_user_created_active` (existing partial index at `libraries/utils/utils/models/user_activity.py:45`); the `imports_actionable` count query adds a new partial index `ix_import_items_user_status_actionable` on the `import_jobs.user_id` JOIN-partner (see Implementation Notes for exact shape).

## Tasks / Subtasks

- [ ] **Task 1** — Add `NOTIFICATION_TAB_TYPES` constant (AC: #1)
  - [ ] Edit `libraries/utils/utils/models/user_activity.py`: add `NOTIFICATION_TAB_TYPES: frozenset[str] = frozenset({"partner_action"})` at module top, after imports.
  - [ ] Docstring: "Single source of truth for user_activity.type values that surface in the Notifications tab and contribute to the bell count. Adding a value here is the only way to make a type user-visible."
- [ ] **Task 2** — Rewrite `unread_count.py` (AC: #2, #3, #4, #7, #10)
  - [ ] Import `NOTIFICATION_TAB_TYPES` + `ImportItem` + `ImportJob`.
  - [ ] Run notifications query first (single `self.db.query(UserActivity).filter(...).count()`).
  - [ ] Run imports_actionable query second — join `import_items` ↔ `import_jobs` on `import_job_id`, filter on `ImportJob.user_id == user.id` and the status set.
  - [ ] Construct `Response(notifications=n, imports_actionable=i, count=n+i)`.
  - [ ] Response model has a deprecation note on `count` (docstring / `Field(description="DEPRECATED — remove after epic-activity-full-history. Equals notifications + imports_actionable.")`).
  - [ ] Module docstring: document sequential execution ("Two counts run back-to-back on one session — no gather; SQLAlchemy sync + shared pool make parallel false economy.").
- [ ] **Task 3** — Apply allow-list in `list_activities.py` (AC: #5, #8)
  - [ ] Import `NOTIFICATION_TAB_TYPES`.
  - [ ] Add `include_system_types: bool = False` kwarg to `execute`.
  - [ ] Wire router: `services/api/src/routers/v1/activity_router.py` `list_activities` — add `include_system_types: bool = Query(False, ...)`.
  - [ ] Branch: if `not include_system_types`, append `UserActivity.type.in_(NOTIFICATION_TAB_TYPES)` to the filter chain.
- [ ] **Task 4** — Admin-gate `?include_system_types` (AC: #9)
  - [ ] Simplest shape: inside the router, after the user is resolved, check `include_system_types and not user.is_admin → raise APIException(403, "Admin access required", ErrorCode.FORBIDDEN)`. Do NOT swap the whole endpoint dependency to `require_admin` (that'd gate the default path too). Raise the 403 BEFORE calling `ListActivities.call`.
- [ ] **Task 5** — Add partial index on `import_items(user_id, status)` via `import_jobs` join (AC: #12)
  - [ ] Because `import_items` has no `user_id` column, the `imports_actionable` query joins to `import_jobs`. Add the pragmatic index: partial index on `import_items(import_job_id, status) WHERE archived_at IS NULL AND dismissed_at IS NULL`. This lets the planner seek `import_job_id`s once `import_jobs.user_id = :me` narrows to that user's jobs.
  - [ ] Migration file: `services/migrator/migrations/versions/<new_rev>_add_import_items_actionable_index.py`. Chain `down_revision` off the current head (`mcal1mealid01`).
  - [ ] Use `op.create_index` (or `op.execute("CREATE INDEX CONCURRENTLY …")` inside `with op.get_context().autocommit_block():` per the ahr-1 pattern — see existing migrations for the exact invocation).
  - [ ] Add matching SQLAlchemy index in `libraries/utils/utils/models/import_item.py` `__table_args__` so `migrator:check-models` stays clean.
- [ ] **Task 6** — Tests (AC: #6, #7, #8, #9, #11)
  - [ ] Rewrite `services/api/tests/test_user_activity.py::TestUnreadCount` for the new payload. Use `mock_db.db.query.side_effect = [notifications_query_mock, imports_query_mock]` pattern OR create separate `MockQuery` per `UserActivity` / `ImportItem` dispatch. See conftest to pick the cleanest shape.
  - [ ] Add `TestListActivitiesAllowList` class — default filter hides import_started, admin `?include_system_types=true` returns it, non-admin with flag returns 403.
  - [ ] Add backward-compat test: response has `count` and `count == notifications + imports_actionable`.
  - [ ] `npx nx run api:test` passes; `npx nx run api:lint` passes.
- [ ] **Task 7** — Local CI gate (ALL must pass before commit)
  - [ ] `npx nx run api:lint`
  - [ ] `npx nx run api:test`
  - [ ] `npx nx run migrator:lint`
  - [ ] `npx nx run migrator:check-models` (alembic drift — required because we touch a model in `libraries/utils/utils/models/import_item.py` AND add a migration)
- [ ] **Task 8** — Status + sprint-status bookkeeping
  - [ ] Set this story Status to `review` after all tasks pass.
  - [ ] Update `_bmad-output/implementation-artifacts/sprint-status.yaml`: `abi-1-…: ready-for-dev → review` (dev-story workflow will do this itself).

## Dev Notes

### Implementation patterns already in the codebase (read before writing)

- **Endpoint base class:** `libraries/utils/utils/api/endpoint.py:55` — `Endpoint` with `execute()` returning `success(data=Model)`; `call()` classmethod is invoked from the router. Keep that shape — don't invent a new pattern.
- **Router pattern:** `services/api/src/routers/v1/activity_router.py:39-45` — `unread_count` is already wired; you're modifying body, not touching registration. For `list_activities` add the new `include_system_types` query param and raise `APIException(403, "Admin access required", ErrorCode.FORBIDDEN)` from the router handler BEFORE `ListActivities.call` if a non-admin passes it.
- **Admin check:** `services/api/src/dependencies.py:199-209` — `require_admin` pattern. Don't re-implement the check; replicate the `APIException` raise inline to keep the non-admin default path un-gated.
- **Archived_at is on Base:** `libraries/utils/utils/models/joins_base.py:20` — every row has `archived_at` / `created_at` / `updated_at` via `JoinsBase`. `is_archived()` helper exists.
- **ImportItem has NO `user_id` column:** `libraries/utils/utils/models/import_item.py` — user is resolved via `import_jobs.user_id`. The `imports_actionable` query MUST join (`self.db.query(ImportItem).join(ImportJob).filter(ImportJob.user_id == user.id, ...)`). The epic's inline SQL suggests `user_id` is on `import_items` — that's wrong; the epic was drafted against a mental model. Follow the code.
- **Existing `ListActivities` retention:** `services/api/src/api/v1/user_activity/list_activities.py:10` — 30-day cutoff already exists (`_ACTIVITY_RETENTION_DAYS`). Reuse it for the `unread_count` notifications query instead of duplicating the `timedelta` constant.
- **Migration pattern:** `services/migrator/migrations/versions/20260418090000_add_meal_id_to_calendar_and_cooking_logs.py` is a good reference for a clean revision file; `20260418070000_add_import_item_s3_key.py` (not yet read) is a closer analog (partial unique index). For `CREATE INDEX CONCURRENTLY`, grep for an existing example in the versions/ directory.
- **Model index declaration:** see `libraries/utils/utils/models/user_activity.py:39-58` for `postgresql_where=text(...)` partial index syntax; mirror that in `import_item.py`.

### ImportItem status values — reconcile epic vs code before writing the query

Epic lists: `('pending','processing','extracting','matching','awaiting_parser','awaiting_review','failed')`.
Codebase (grepped across `libraries/utils/utils/tasks/import_tasks/`) actually assigns: `pending | extracting | matching | awaiting_review | approved | completed | failed`. `processing` and `awaiting_parser` are **ImportJob** statuses, not ImportItem statuses.

**Decision:** use the set that matches what the pipeline actually writes to `import_items`:
```
ACTIONABLE_IMPORT_STATUSES = frozenset({
    "pending", "extracting", "matching", "awaiting_review", "failed",
})
```
This is what "actionable" means on the Imports tab today (in-progress + needs-review + failed). It is narrower than the epic text; that's intentional — including job-level states here would never match a row.

Put this constant in `libraries/utils/utils/models/import_item.py` (same pattern as `NOTIFICATION_TAB_TYPES`) so the count query imports it and a future per-tab-filter can re-use it.

### Backward-compat `count` wrapper — why keep it

The Flutter client on a shipped build still reads `response.data['count']` (see `app/lib/features/activity/providers/activity_read_provider.dart:110`). Until abi-3 ships and one release of soak passes, old installs reading the new server will still want `count`. Remove the wrapper in the release after `epic-activity-full-history`.

### Sequential queries — don't be clever

`asyncio.gather` would require two sessions or careful single-session multiplexing; SQLAlchemy sync sessions don't buy anything from it on a shared pool. Two back-to-back `.count()` calls on one session complete in <5ms on warm indexes. Leave it simple; document the choice in the endpoint docstring.

### Testing — conftest pattern

`services/api/tests/test_user_activity.py` already uses `MockQuery` + `mock_db.db.query.return_value`. For the new dual-count endpoint, **two separate query classes are hit** — `UserActivity` and `ImportItem`. Either:
- (a) set `mock_db.db.query.side_effect = [notif_query, imports_query]` returning the right `MockQuery` in order, OR
- (b) use a custom `side_effect` callable that dispatches on the arg: `lambda m: notif_query if m is UserActivity else imports_query`.

Prefer (b) — order-independent and robust to later reorderings. Check `services/api/tests/conftest.py` for `MockQuery` signature before writing.

### Router — default path NOT admin-gated

The ask: `/v1/activities?include_system_types=true` requires admin; `/v1/activities` (no flag) must not. Implementation:

```python
@activity_router.get("")
async def list_activities(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
    limit: int = 50,
    offset: int = 0,
    include_archived: bool = Query(False, ...),
    include_system_types: bool = Query(False, ...),
):
    if include_system_types and not user.is_admin:
        raise APIException(
            status_code=403,
            detail="Admin access required",
            code=ErrorCode.FORBIDDEN,
        )
    return ListActivities.call(...)
```

Do NOT switch the whole handler to `Depends(require_admin)` — that'd 403 every default call.

### Coverage guard

`project_api_coverage_100.md` memory: `services/api` is pinned at 100%. Any uncovered line breaks CI. Make sure every branch of the new `unread_count.py` and the admin-gate branch have tests. `migrator:check-models` is also load-bearing — it'll fail CI if the `import_item.py` model has the new Index declaration but the migration hasn't been generated.

### Project Structure Notes

- `services/api/src/api/v1/user_activity/` — no per-module tests directory; all user-activity tests live in `services/api/tests/test_user_activity.py`. Keep that convention.
- `libraries/utils/utils/models/` is the cross-service home for SQLAlchemy models and the associated tiny constants (allow-lists, enums). Epic wanted `NOTIFICATION_TAB_TYPES` here (not `services/api/src/constants.py`) explicitly so the import-task workers can read it without reaching up into `services/api`.

### References

- Epic: `_bmad-output/planning-artifacts/epic-activity-badge-integrity.md#Story-abi-1`
- Unread-count endpoint: `services/api/src/api/v1/user_activity/unread_count.py`
- List activities endpoint: `services/api/src/api/v1/user_activity/list_activities.py`
- UserActivity model: `libraries/utils/utils/models/user_activity.py`
- ImportItem model: `libraries/utils/utils/models/import_item.py`
- Router: `services/api/src/routers/v1/activity_router.py`
- Tests: `services/api/tests/test_user_activity.py`
- Admin pattern: `services/api/src/dependencies.py:199`
- Recent migration example: `services/migrator/migrations/versions/20260418090000_add_meal_id_to_calendar_and_cooking_logs.py`

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

### Completion Notes List

### File List
