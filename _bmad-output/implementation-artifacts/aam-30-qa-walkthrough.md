# aam-30 — Recurrence Rule Domain Async — QA Walkthrough

**Story:** [aam-30-recurrence-rule-domain-async](aam-30-recurrence-rule-domain-async.md)
**Date:** 2026-04-24

## Verification checklist

- [x] All 5 recurrence_rule endpoints inherit `AsyncEndpoint`, `async def execute`, await DB calls
- [x] Router handlers are `async def` with `get_current_user_async` + `get_async_database`
- [x] `_run_materialize` + `_materialize_sync` defined in both create + update modules
- [x] Calendar access via `require_calendar_access_async` everywhere
- [x] Multi-calendar scope via `get_user_calendar_ids_async`
- [x] Meal availability via `require_meal_available_async`
- [x] `test_recurrence_rule.py` rewritten to `mock_async_db` pattern (75 tests)
- [x] `test_recurrence_rule_with_meals.py` rewritten (11 tests)
- [x] No tests deleted; every original test name preserved
- [x] Per-file coverage on `services/api/src/api/v1/recurrence_rule/` = 100%
- [x] `npx nx run api:lint` green
- [x] sprint-status flipped `aam-30-recurrence-rule-domain-async` → `done`

## Endpoints converted (5)

| Endpoint | DB calls (async) | Materialize dispatch |
|---|---|---|
| `ListRecurrenceRules` | get_user_calendar_ids_async OR require_calendar_access_async; rules SELECT; optional Meal batch SELECT | — |
| `GetRecurrenceRule` | find_by rule + require_calendar_access_async; optional Meal SELECT for hydration | — |
| `CreateRecurrenceRule` | require_calendar_access_async; optional Recipe find_by; optional require_meal_available_async (2 SELECTs); flush + commit + refresh | 1× threadpool dispatch after commit |
| `UpdateRecurrenceRule` | find_by rule; require_calendar_access_async; optional Recipe find_by; optional require_meal_available_async; optional 2nd require_calendar_access_async + bulk UPDATE for move-to-calendar; flush + commit + refresh | 1× (scope=all) or 2× (scope=this_and_following) threadpool dispatches after commit |
| `DeleteRecurrenceRule` | find_by rule; optional fallback SELECT for archived rule; require_calendar_access_async; per-scope DELETE/SELECT; commit | — |

## Atomicity trade-off

For `CreateRecurrenceRule` and `UpdateRecurrenceRule`, the async session is committed BEFORE materialize is dispatched into the threadpool. This means:

- If the threadpool materialize fails, the rule (or split rules) are durable on disk but their initial window of `meal_events` is missing.
- The nightly materialization worker (`services/worker/...`) is the authoritative fallback and will fill in the gaps.
- This matches the precedent established in `api/v1/meal_event/list_meal_events._run_materialize`.
- For `scope=this_and_following`, partial materialize failures (old rule re-materialized but new rule failed) leave dangling meal_events past `split_end` until the worker reconciles.

The trade-off is documented in the story file's "Out-of-Scope Callouts / Gotchas" section.

## Manual smoke (post-deploy plan)

The user can run these requests against staging to validate the conversion:

```bash
# Create a freetext rule on the default calendar
curl -X POST $API/v1/recurrence-rules -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"Pasta","calendar_id":"<cal>","meal_type":"dinner","weekdays":["fri"],"interval":"weekly","start_date":"2026-04-25","tz_name":"America/Los_Angeles","is_shared":false}'

# List the rules
curl $API/v1/recurrence-rules -H "Authorization: Bearer $TOKEN"

# Update with scope=all
curl -X PUT $API/v1/recurrence-rules/<rule_id> -H "Authorization: Bearer $TOKEN" \
  -d '{"scope":"all","title":"Pasta Friday"}'

# Delete with scope=series
curl -X DELETE $API/v1/recurrence-rules/<rule_id> -H "Authorization: Bearer $TOKEN"
```

Expected: every request returns within ~200ms (event loop unblocked); GET `/v1/recurrence-rules` p95 should improve vs the Phase 0 threadpool baseline.

## Test results (local)

```
$ npx nx run api:test -- tests/test_recurrence_rule.py tests/test_recurrence_rule_with_meals.py
75 passed in 10.13s

$ npx nx run api:lint
All checks passed!

$ pytest --cov=src/api/v1/recurrence_rule --cov=src/routers/v1/recurrence_rule_router
Required test coverage of 100.0% reached. Total coverage: 100.00%
```

## Files changed (8)

- `services/api/src/api/v1/recurrence_rule/create_recurrence_rule.py`
- `services/api/src/api/v1/recurrence_rule/delete_recurrence_rule.py`
- `services/api/src/api/v1/recurrence_rule/get_recurrence_rule.py`
- `services/api/src/api/v1/recurrence_rule/list_recurrence_rules.py`
- `services/api/src/api/v1/recurrence_rule/update_recurrence_rule.py`
- `services/api/src/routers/v1/recurrence_rule_router.py`
- `services/api/tests/test_recurrence_rule.py`
- `services/api/tests/test_recurrence_rule_with_meals.py`

## Story artifacts

- `_bmad-output/implementation-artifacts/aam-30-recurrence-rule-domain-async.md` — story file
- `_bmad-output/implementation-artifacts/aam-30-qa-walkthrough.md` — this file
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flipped to `done`
