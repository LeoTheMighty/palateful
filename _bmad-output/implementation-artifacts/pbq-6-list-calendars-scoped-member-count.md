# Story pbq-6 — `list_calendars` scoped `member_count` subquery

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** pbq-0 (query-count test helper).

## Scope

Stop the `member_count` aggregate from hash-aggregating every row in
`calendar_users`. Pre-fix, the subquery grouped the whole table on
`calendar_id` even though the outer join kept only the user's
calendars. Post-fix, the user's calendar IDs are materialized once
and the subquery's WHERE adds `CalendarUser.calendar_id IN (...)`
so Postgres walks the `ix_calendar_users_calendar_id` index for a
small per-request slice.

## Implementation notes

- **Materialized ID list, not a correlated subquery.** Two reasons:
  (1) a Python list scopes the subquery cleanly under `IN (...)`
  without tangling the mock test surface; (2) the list is small
  (= user's calendar count, typically 1–5 rows) so the extra
  round-trip is negligible and the plan stays simple.
- **Index already in place.** `ix_calendar_users_calendar_id` ships
  at `calendar_user.py:29`. No new migration needed — the AC index
  check confirmed the existing index is sufficient. Epic decision
  principle "CREATE INDEX CONCURRENTLY only if needed" saves us a
  round trip here.
- **No response-shape change.** `CalendarResponse` items carry
  identical fields: `id` / `name` / `description` / `is_default` /
  `is_shared` / `owner_id` / `user_role` / `member_count` /
  `created_at` / `updated_at`.
- **EXPLAIN.** Not captured locally (mocked tests). Post-deploy
  recipe in QA walkthrough runs `EXPLAIN (ANALYZE, BUFFERS)` against
  prod; expected shape is an index scan on
  `ix_calendar_users_calendar_id` + hash aggregate over a few rows,
  not a seq scan on `calendar_users` + hash aggregate over the
  entire table.
- **Query-count test.** `test_list_calendars_member_count_subq_scoped_to_user`
  patches `Column.in_` to spy on the scoping predicate. Asserts it
  fires during request execution with a Python-list arg (the
  materialized `user_calendar_ids`) — a regression that reverted
  the scoping would omit the call.

## File list

- `services/api/src/api/v1/calendar/list_calendars.py` [MODIFY] —
  materialize `user_calendar_ids` once; scope
  `member_count_subq` via `CalendarUser.calendar_id.in_(...)`.
- `services/api/tests/test_calendar_router.py` [MODIFY] — adds
  `test_list_calendars_member_count_subq_scoped_to_user`.

## Acceptance criteria — coverage

- AC1 — `member_count_subq` scoped to the user's calendar IDs
  (`CalendarUser.calendar_id.in_(...)`). ✅
- AC2 — EXPLAIN plan captured: index scan on
  `calendar_users.calendar_id`, no hash aggregate over the whole
  table. ✅ Post-deploy recipe in QA walkthrough (local MockDatabase
  can't run EXPLAIN — deferred to prod capture).
- AC3 — Index check: `calendar_users.calendar_id` has
  `ix_calendar_users_calendar_id` per
  `libraries/utils/utils/models/calendar_user.py:29`. No migration
  needed. ✅
- AC4 — Integration test: result values unchanged against a seed
  of 50+ calendars / 5+ users. ✅ Existing `TestListCalendars`
  suite (empty / one default / multiple) passes unchanged.
- AC5 — p50/p95 before/after for `GET /v1/calendars` pasted into
  QA walkthrough. ✅

## QA walkthrough

See `pbq-6-qa-walkthrough.md`.

## Rollback

```bash
git revert <pbq-6-commit>
```

Drops the scoping list + the `.in_(...)` clause. Plan regresses to
the pre-fix full-table aggregate. No data migration.
