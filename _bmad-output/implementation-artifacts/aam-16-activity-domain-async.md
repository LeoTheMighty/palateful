# Story aam-16: Activity domain async

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 3 — Per-domain conversions

## Acceptance Criteria

1. `libraries/utils/utils/services/activity_service.py` — sync
   `create_activity(db, ...)` kept as-is for currently-sync callers
   (worker tasks + recipe-book + shopping-list endpoints which are
   still on sync until aam-11/aam-13); add twin
   `create_activity_async(db, ...)` that accepts an `AsyncSession` and
   `await`s the flush. Callers inside already-async handlers adopt the
   async twin now; sync callers stay on the sync function until their
   domains flip. This is the same dual-surface pattern aam-10 used for
   `aggregate_meal_ingredients` / `aggregate_meal_ingredients_async`.
2. `services/api/src/api/v1/user_activity/*.py` — every `Endpoint`
   subclass converts to `AsyncEndpoint`; `execute` becomes `async def`;
   every `self.db.*` / `self.database.*` call is awaited where it
   crosses the session boundary (`.find_by`, `.execute`, `.commit`,
   `.flush`, `.count()` on `AsyncQuery`).
3. `services/api/src/api/v1/user_activity/list_activities.py` —
   `self.db.query(UserActivity).filter(...).limit(limit + 1).all()` →
   `await self.db.execute(select(UserActivity).where(...).limit(limit + 1))`;
   `.count()` on the ffm-4 unread-count snapshot also converts. Order
   of counts and filters preserved.
4. `services/api/src/api/v1/user_activity/mark_all_read.py` — bulk
   `self.db.query(UserActivity).filter(...).update({"read": True})` →
   `await self.db.execute(sa_update(UserActivity).where(...).values(read=True))`.
   Commit still required (flush alone is rolled back on session close).
5. `services/api/src/api/v1/user_activity/unread_count.py` — both count
   queries (notifications + imports_actionable) convert to
   `await AsyncQuery(...).count()` or `select(func.count())` scalar.
   Tenant isolation filter set (user_id, read, archived_at, type,
   created_at, join-to-ImportJob, status, dismissed_at) preserved
   byte-for-byte — the test spy asserts every clause.
6. `services/api/src/api/v1/user_activity/see_all_count.py` — both
   count queries async; COALESCE / `archived_at.isnot(None)` filters
   unchanged.
7. `services/api/src/routers/v1/activity_router.py` —
   `Depends(get_database)` → `Depends(get_async_database)`;
   `Depends(get_current_user)` → `Depends(get_current_user_async)`;
   every `return Foo.call(...)` → `return await Foo.call(...)`; every
   route handler becomes `async def`. The `since_days=""` parse branch
   that raises a 400 is preserved; the custom `HTTPException` raise
   stays synchronous (it doesn't cross the event loop).
8. **pbq-5 contract preserved**: `total=0` still dropped on the
   cursor-less path; no `COUNT(*)` on `user_activities` in
   `ListActivities`. Grep verified no Flutter consumer of
   `/v1/activities`'s `total` field — only
   `/v1/activities/see-all-count` reads `total`, which is a separate
   endpoint.
9. `services/api/tests/test_user_activity.py` — converts to
   `async_client` style via the existing sync `client` fixture +
   `mock_async_db.db.execute.side_effect`. `mock_db.db.query` seeds
   become `mock_async_db.db.execute.side_effect = [...]` lists of
   `MockExecuteResult`. `set_find_by` / `set_where` helpers carry over
   unchanged — `MockAsyncDatabase` mirrors the sync helper surface.
   The `FilterSpyQuery` tests (pbq-5 + allow-list behavioural spies)
   convert to a select-spy equivalent or to asserting on the compiled
   SQL string — aam-10 pattern: assert against `str(stmt)` on the
   captured `execute` arg.
10. **Lazy-load audit** — grep output confirming no `user_activity`
    handler reaches into a related-model attribute that would trigger
    `MissingGreenlet` on the async engine. `UserActivity` has no
    relationships used on the read paths (only scalar columns). Imports
    domain rows in `unread_count.py` (`ImportItem.join(ImportJob)`) are
    explicit SQL joins, not lazy attribute traversals. Output pasted in
    QA walkthrough.
11. `GET /v1/activities` baseline captured via `bin/prod-script
    services/api/scripts/analyze_latency.py --window 24h` before PR
    opens; post-merge 24h capture target: client-observed p95 flat or
    improved. The endpoint's mounting cost on-stack is already small
    relative to the sync-over-async threadpool tax fallen on all the
    pre-aam-16 handlers, so the expected change is modest but positive.
12. Worker contract gate: `services/worker/`, `services/parser/`, and
    `libraries/utils/utils/tasks/` all still build + import.
    Specifically verified: `parser_batch_completion.py` and
    `watch_parser_job_task.py` still use sync `create_activity` and run
    unchanged (tested via `poetry run pytest libraries/utils/` after
    the change).
13. 100% API coverage preserved.

## File List

### Modified
- `libraries/utils/utils/services/activity_service.py` — adds
  `create_activity_async` twin. Sync `create_activity` unchanged.
- `services/api/src/api/v1/user_activity/__init__.py` — re-exports
  unchanged; underlying classes now inherit `AsyncEndpoint`.
- `services/api/src/api/v1/user_activity/archive_activity.py` — async.
- `services/api/src/api/v1/user_activity/list_activities.py` — async;
  two `select(UserActivity)` statements (main list + ffm-4 unread
  snapshot).
- `services/api/src/api/v1/user_activity/mark_activity_read.py` —
  async.
- `services/api/src/api/v1/user_activity/mark_all_read.py` — async;
  bulk UPDATE via Core `update(...).where(...).values(read=True)`.
- `services/api/src/api/v1/user_activity/see_all_count.py` — async;
  two `select(func.count())` statements.
- `services/api/src/api/v1/user_activity/unarchive_activity.py` —
  async.
- `services/api/src/api/v1/user_activity/unread_count.py` — async;
  notifications `select(func.count())` + imports join select.
- `services/api/src/routers/v1/activity_router.py` — async deps +
  `await Foo.call(...)`.
- `services/api/tests/test_user_activity.py` — `mock_async_db` +
  `mock_async_db.db.execute.side_effect` seeding. `FilterSpyQuery`
  replaced with select-stmt spy on the `execute.call_args_list` (same
  assertion semantics, new capture point).

### New
- `_bmad-output/implementation-artifacts/aam-16-qa-walkthrough.md` —
  lazy-load audit, baseline table, 7-scenario QA checklist, rollback
  procedure.

## Notes

- **Activity_service deviates from the meal pattern in one subtle
  way**: the service function calls `db.flush()` (but not `commit()`)
  because the caller's endpoint is expected to commit. In the async
  twin, `await db.flush()` is correct — the caller (which will be an
  async `Endpoint`) will `await db.commit()` at end-of-execute. This
  matches the sync semantics method-for-method.

- **Rollback path**: matches aam-10 / aam-21 precedent — rollback
  during the observation window is `git revert <aam-16-commit> &&
  bin/prod-deploy` (~10 min), not a registration flip. aam-10's
  rationale (single-user traffic makes the 5-minute differential
  negligible; avoiding dual-register shim churn) applies equally here.
  Last-good commit before aam-16: `4ea2212` (aam-foundations notify
  threadpool helper).

- **ffm-4 unread_count snapshot**: the second query inside
  `ListActivities.execute` is a `.count()` on a filtered
  `UserActivity` select. `AsyncQuery.count()` already wraps the stmt
  in `select(func.count()).select_from(stmt.subquery())` — same
  semantics as sync SQLAlchemy's `.count()`. The test assertion that
  there are **two** `UserActivity` queries on the list path (the main
  LIST + the unread_count snapshot) becomes an assertion on the
  number of `execute(...)` calls that took a select rooted in
  `UserActivity`. Same load-bearing check, new capture.

- **pbq-5 `total=0` contract**: the server still sets
  `total=0` on the cursor-less path without firing any COUNT query.
  Verified no Flutter consumer reads `/v1/activities`'s `total` field
  (grep `app/lib/features/activity/**/*.dart` for `'total'` — only
  `see_all_count_provider.dart` matches, and that reads from the
  separate `/v1/activities/see-all-count` endpoint). Response schema
  keeps the `total: int` field (unchanged) so the pydantic contract
  stays stable.

- **FilterSpyQuery migration**: the three behavioural-spy tests that
  verify "the allow-list filter lands", "tenant isolation lands", and
  "admin path drops the allow-list" switch from capturing
  `.filter(...)` args on the mock query to capturing the `select(...)`
  statement on the first arg of `db.execute(...)`. Assertion becomes
  "`str(captured_stmt)` contains `user_activities.type` IN (...)".
  Same invariants covered; different capture surface.

- **Advisory locks / concurrency**: none of the activity endpoints
  use `Database.lock(...)` or `find_or_create_by`, so there's no
  advisory-lock async-migration work in this story.

- **Coverage**: 100% enforced; any untested branch fails CI. No
  legacy router or sync shim is added — precedent set by aam-10 and
  aam-21.
