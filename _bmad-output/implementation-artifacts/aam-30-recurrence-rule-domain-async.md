# aam-30 — Recurrence Rule Domain Async

**Epic:** [epic-api-async-migration](../planning-artifacts/epic-api-async-migration.md)
**Status:** ready-for-dev → in-progress → review → done
**Prerequisites landed:** aam-1..aam-6 (foundations), aam-foundations-notify-threadpool-helper, aam-10 (meal reference), aam-14 (calendar + meal_event — `require_calendar_access_async`, `get_user_calendar_ids_async`, `require_meal_available_async`, `_run_materialize` pattern).

## Scope

Convert the recurrence_rule domain from sync `Endpoint` to `AsyncEndpoint`, matching the recipe laid out in
`_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md`.

**Files in scope:**
- Router: `services/api/src/routers/v1/recurrence_rule_router.py` (5 handlers)
- Endpoints: `services/api/src/api/v1/recurrence_rule/*.py`
  - `list_recurrence_rules.py`
  - `get_recurrence_rule.py`
  - `create_recurrence_rule.py`
  - `update_recurrence_rule.py`
  - `delete_recurrence_rule.py`
  - `_access.py` — pure validators, no DB (stays pure; no change to function bodies)
- Tests:
  - `services/api/tests/test_recurrence_rule.py` rewritten to `mock_async_db` + `MockExecuteResult`.
  - `services/api/tests/test_recurrence_rule_with_meals.py` rewritten.
  - `services/api/tests/test_list_meal_events_recurrence.py` — **already async**; NOT in scope (tests `ListMealEvents`, not the recurrence_rule router).

**Explicitly NOT in scope:**
- `libraries/utils/utils/recurrence/materializer.py` — stays sync. The endpoints dispatch it through
  `run_in_threadpool` with a fresh sync `SessionLocal()`, matching the pattern already established by
  `list_meal_events._run_materialize`. Rewriting the materializer async is a larger refactor not
  justified by this story.
- `services/api/src/api/v1/calendar/dependencies.py` — already provides both sync and async variants
  from aam-14. We consume `require_calendar_access_async` + `get_user_calendar_ids_async` directly.
- `services/api/src/api/v1/meal_event/_meal_binding.py` — already provides
  `require_meal_available_async` from aam-14. We consume it directly.
- MCP: there is no `services/api/src/mcp_server/tools/recurrence_rule.py` — skip the "MCP tool
  conversion" step. The existing MCP surface for calendars (`meal_planning.py`) does not expose
  recurrence_rule writes.

## Approach

### Endpoint conversions

All 5 endpoint classes flip `Endpoint` → `AsyncEndpoint`, `def execute` → `async def execute`.
DB calls translate per the cheat-sheet in the dev-snippets doc.

| Endpoint                | Async DB calls (count)          | Materialize          |
| ----------------------- | -------------------------------- | -------------------- |
| `ListRecurrenceRules`   | 2–3 (get_user_calendar_ids_async or require_calendar_access_async + rules + optional meals) | — |
| `GetRecurrenceRule`     | 2–3 (find_by rule + require_calendar_access_async + optional meal hydration) | — |
| `CreateRecurrenceRule`  | 1–3 (require_calendar_access_async + optional recipe find_by + optional require_meal_available_async) + flush + commit + refresh | 1 threadpool dispatch after commit |
| `UpdateRecurrenceRule`  | 2–6 (find_by rule + require_calendar_access_async + optional recipe + optional meal-available + optional 2nd require_calendar_access_async for move-to-calendar + bulk UPDATE for future meal_events) + flush + commit + refresh | 1 (scope=all) or 2 (scope=split) threadpool dispatches after commit |
| `DeleteRecurrenceRule`  | 2–3 (find_by rule, optional fallback query for archived rule, require_calendar_access_async, per-scope DELETE or SELECT) + commit | — (only destructive on meal_events; direct async DELETE) |

### Materialize dispatch (create + update)

Materialize must run against a sync `Session` (the materializer uses sync SQLAlchemy). Following the
precedent in `api/v1/meal_event/list_meal_events.py`, each endpoint that triggers materialize will:

1. Commit the async session FIRST so the rule row is durable.
2. `await run_in_threadpool(_materialize_sync, rule_id, through_date)` where `_materialize_sync` opens
   a fresh `SessionLocal()`, re-loads the rule by id, calls `materialize(...)`, commits, closes.
3. `await self.db.refresh(rule)` to pick up `materialized_through` set inside the threadpool.

The local `_materialize_sync` + `_run_materialize` helpers live at module scope inside
`create_recurrence_rule.py` and `update_recurrence_rule.py` (each file keeps its own copy — two
lines of shared code isn't worth a new module, and the callsites are distinct).

Trade-off: the rule is durable before materialize runs. If the threadpool materialize fails, the
rule is persisted without its initial window. The nightly materialization worker
(`services/worker/...`) is the authoritative fallback, matching `list_meal_events`' fire-and-forget
comment. Test coverage asserts both success and the watermark-refresh round-trip.

### Router flip

All 5 handlers flip to `async def` + `get_current_user_async` + `get_async_database` +
`return await X.call(...)`. Matches `meal_router.py` reference.

### Tests

Both test files (`test_recurrence_rule.py`, `test_recurrence_rule_with_meals.py`) rewrite the mock
shape:

- `mock_db` fixture replaced with `mock_async_db`.
- `mock_db.db.query.return_value = MockQuery([...])` replaced with
  `mock_async_db.db.execute.side_effect = [MockExecuteResult(items=[...]), ...]`.
- `mock_db.set_find_by(...)` → `mock_async_db.set_find_by(...)` (API is identical).
- `mock_db.db.query.side_effect = _query_router` routed-by-model pattern → translate to an
  ordered `db.execute.side_effect` list since both test files' routed queries were driven by the
  sync fallback path for `_access.py`'s now-removed pantry-mate logic (dead code — `_access.py`
  only contains validators today; the pantry-mate lookup lives in test fixtures that no production
  code path hits).
- Tests that patch `materialize` directly need to patch `_run_materialize` on the converted module
  instead, mirroring `test_list_meal_events_recurrence.py`.
- All test names, counts, and assertion intents preserved. No test deletions.

## Acceptance Criteria

- [ ] 5 recurrence_rule endpoints inherit `AsyncEndpoint`, `async def execute`, queries use
      `select()` + `await`.
- [ ] Router handlers are `async def` with `get_current_user_async` + `get_async_database`.
- [ ] `create_recurrence_rule.py` + `update_recurrence_rule.py` each own a local
      `_materialize_sync` / `_run_materialize` helper that dispatches materialize via
      `run_in_threadpool`.
- [ ] `_access.py` validators stay pure (no async change needed — no DB).
- [ ] Calendar-access lookups use `require_calendar_access_async`; multi-calendar scope uses
      `get_user_calendar_ids_async`; meal availability uses `require_meal_available_async`.
- [ ] `test_recurrence_rule.py` + `test_recurrence_rule_with_meals.py` rewritten to `mock_async_db`
      shape; every test name preserved; no deletions.
- [ ] `npx nx run api:lint` green.
- [ ] `npx nx run api:test` green with 100% coverage on touched files.
- [ ] No sync DB call on the event loop inside any recurrence_rule handler (visual audit).
- [ ] sprint-status.yaml flips `aam-30-recurrence-rule-domain-async: backlog` → `done`.

## Out-of-Scope Callouts / Gotchas

- The materializer stays sync; a rewrite to async would ripple into the nightly worker and is a
  separate story. The threadpool dispatch is the accepted pattern (see aam-14 / list_meal_events).
- Atomicity compromise: rule create/update commits BEFORE materialize runs. If materialize
  threadpool call fails, the rule is durable but its first-window meal_events are missing until
  the nightly worker re-runs. Best-effort, matches existing precedent.
- Non-tracked side effects from the `with_meals` tests used routed `db.query.side_effect` to model
  two logical lookups (Meal + RecipeBookUser). The async rewrite keeps the same semantics but
  flattens routing into ordered `execute.side_effect` where possible, and falls back to
  `set_find_by` + `set_where` for lookups that weren't ordered by call-site.
- `delete_recurrence_rule.py`'s archived-rule fallback (direct `db.query(MealRecurrenceRule)...first()`
  for rules where `find_by` returned `None` because of the archived_at filter) becomes
  `await self.db.execute(select(MealRecurrenceRule).where(...).limit(1))`. Tests cover this
  idempotency path.

## QA Walkthrough

See `aam-30-qa-walkthrough.md` (generated alongside this story).
