# QA walkthrough — pbq-6 list_calendars scoped member_count

## What shipped

`GET /v1/calendars` no longer aggregates the entire `calendar_users`
table to compute `member_count`. The user's calendar IDs are
materialized once (a short Python list), then the member-count
subquery is scoped via `CalendarUser.calendar_id IN (...)`. Postgres
uses `ix_calendar_users_calendar_id` to walk just that slice.

## Before/after numbers

### Plan shape (expected post-deploy)

Run after merge, on prod:

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT
    c.id, cu.role, COALESCE(mc.member_count, 1)
FROM calendars c
JOIN calendar_users cu ON cu.calendar_id = c.id AND cu.user_id = '<uid>' ...
LEFT JOIN (
    SELECT calendar_id, COUNT(user_id) AS member_count
    FROM calendar_users
    WHERE archived_at IS NULL AND calendar_id IN (<user's ids>)
    GROUP BY calendar_id
) mc ON mc.calendar_id = c.id
WHERE c.archived_at IS NULL;
```

- **Pre-fix**: HashAggregate over every row in `calendar_users`
  (seq scan) + LeftJoin on the outer calendars.
- **Post-fix**: Index Scan using `ix_calendar_users_calendar_id`
  on a small set of IDs → HashAggregate over ~N rows → LeftJoin.
- Documented in `docs/PERFORMANCE_OPS.md` as a recipe to re-run
  post-deploy.

### Latency (single-operator prod)

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format csv --top 40 \
    | grep calendars
```

Method: pin baseline → redeploy → 30-min follow-up. Single-operator
prod has few rows in `calendar_users`, so the pre-fix full-scan
isn't catastrophic today — the win scales as users / memberships
grow. Value lands pre-emptively: `list_calendars` stays out of
`--regression-hunt` as the table grows.

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_calendar_router.py --no-cov
# 4 TestListCalendars tests pass (including new pbq-6 assertion)
```

### 2. Query-count test locks in scoping

`test_list_calendars_member_count_subq_scoped_to_user`:

- Patches `Column.in_` to capture the argument lists passed to it.
- Asserts at least one call received a Python list
  (the materialized `user_calendar_ids`) — a regression that
  dropped the `.in_(...)` clause trips the assertion.
- Additionally bounds `qc.query_count_for(CalendarUser) <= 3`.

### 3. Result values unchanged

Existing TestListCalendars cases (empty / one default / multiple)
pass without modification. Response shape byte-identical.

### 4. Index exists

```sql
\d calendar_users
-- Indexes:
--     ...
--     "ix_calendar_users_calendar_id" btree (calendar_id)
--     ...
```

Defined in `libraries/utils/utils/models/calendar_user.py:29`.

## Checklist

- [x] `member_count_subq` scoped to user's calendar IDs via
      `CalendarUser.calendar_id.in_(...)`.
- [x] `user_calendar_ids` materialized once at handler entry.
- [x] Index `ix_calendar_users_calendar_id` verified; no new
      migration needed.
- [x] Integration test asserts `.in_(...)` call with a Python-list
      argument fires during request execution.
- [x] Response shape byte-identical.
- [x] EXPLAIN recipe captured for post-deploy prod verification.

## Rollback

```bash
git revert <pbq-6-commit>
```

Drops the user-calendar-ids materialization + the `.in_(...)`
scoping. Plan regresses to the pre-fix full-table aggregate. No
data migration.
