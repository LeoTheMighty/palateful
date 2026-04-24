# aam-foundations-notify-threadpool-helper — QA Walkthrough

**Story:** `aam-foundations-notify-threadpool-helper`
**Date:** 2026-04-24

## Summary

Shipped a single helper — `notify_via_threadpool(fn, *args, **kwargs)` —
that every converted `AsyncEndpoint` will use to fan out to the existing
sync notification helpers (`notify_book_shared`, `notify_import_needs_review`,
`notify_meal_event_updated`, etc.). The helper:

- builds a fresh sync `Database(db=SessionLocal())` on the threadpool
  thread (not the event loop),
- injects it as the `database=` kwarg to `fn`,
- closes the session in a `finally` (even on exception),
- swallows any exception from `fn` and logs it to `error_logs` with
  `service='push_notifications'` via the dedicated
  `ErrorLogSessionLocal` sub-pool when available,
- rejects caller-supplied `database=` via an up-front `TypeError`.

Reference sync callsite pattern (before this story) in `aam-phase1-dev-snippets.md`
§ 3 is now one line of async-side code plus the existing sync helper —
D-01..D-13 can adopt it without writing their own `_sync_side_effect` closure.

## Files

| File | Status | Purpose |
|---|---|---|
| `libraries/utils/utils/services/notifications_bridge.py` | new | `notify_via_threadpool` + `_invoke_sync` + `_log_bridge_failure` |
| `libraries/utils/test/test_notifications_bridge.py` | new | 14 unit tests (see table below) |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | `aam-foundations-notify-threadpool-helper: backlog → done` |
| `_bmad-output/implementation-artifacts/aam-foundations-notify-threadpool-helper.md` | new | story spec |
| `_bmad-output/implementation-artifacts/aam-foundations-notify-threadpool-helper-qa-walkthrough.md` | new | this file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 Helper exists | import + 14 tests pass | `test_notifications_bridge.py` all |
| AC #2 Threadpool dispatch | `test_runs_via_run_in_threadpool` | patches `run_in_threadpool` with AsyncMock, asserts awaited once |
| AC #3 Session always closed | `test_session_closed_on_success`, `test_session_closed_on_exception_and_no_reraise` | asserts `closed is True` on the fn-session after both happy and error paths |
| AC #4 Exception swallowed + logged | `test_exception_logs_error_row_with_push_service`, `test_stack_trace_is_real_for_fn_exception` | asserts row `service='push_notifications'`, `error_type='ValueError'`, fn name + error text in message, real stack trace |
| AC #5 Reserved-kwarg guard | `test_reserved_database_kwarg_raises_typeerror` | `pytest.raises(TypeError)` with regex match |
| AC #6 Fallback to main engine | `test_error_log_falls_back_to_default_engine_when_sub_pool_missing` | with `ErrorLogSessionLocal=None`, asserts `Database()` built with empty kwargs |
| AC #7 Graceful when SessionLocal is None | `test_session_local_missing_logs_runtime_error`, `test_stack_trace_is_not_nonetype_for_fabricated_error` | fn never called; row has `error_type='RuntimeError'` with real-looking stack |
| AC #8 Error-log write failures swallowed | `test_error_log_write_failure_is_swallowed` | second Database instance raises on create; helper returns None |
| AC #9 Lint + tests | `nx run utils:lint` (+ `api:lint`), `nx run utils:test` (+ `api:test`) | all green |
| AC #10 Sprint-status flipped | `git diff` sprint-status.yaml | `backlog → done` |

## Test inventory (14 tests, all passing)

| # | Test | What it proves |
|---|---|---|
| 1 | `test_happy_path_injects_database_kwarg` | Injected `database=` is the patched Database built from `SessionLocal()`; non-reserved kwargs forwarded; returns None. |
| 2 | `test_session_closed_on_success` | Exactly one Database built for the fn call; closed after. |
| 3 | `test_session_closed_on_exception_and_no_reraise` | `close()` called even on fn exception; helper returns None. |
| 4 | `test_exception_logs_error_row_with_push_service` | Failure row: `service='push_notifications'`, `error_type` = exception class, message contains fn name + str(exc). |
| 5 | `test_reserved_database_kwarg_raises_typeerror` | `database=` kwarg rejected synchronously before threadpool hop. |
| 6 | `test_error_log_uses_error_log_engine_when_available` | Error-log session built from `ErrorLogSessionLocal` sub-pool when set. |
| 7 | `test_error_log_falls_back_to_default_engine_when_sub_pool_missing` | `Database()` (default engine) when `ErrorLogSessionLocal` is None — worker/script compatibility. |
| 8 | `test_session_local_missing_logs_runtime_error` | `SessionLocal=None`: fn never called, failure row logged with `RuntimeError`. |
| 9 | `test_error_log_write_failure_is_swallowed` | Meta-failure (error-log insert itself blows up) does not propagate. |
| 10 | `test_positional_args_forwarded` | Positional args flow through (helpers with `database` as first-positional still work). |
| 11 | `test_runs_via_run_in_threadpool` | Dispatches through `fastapi.concurrency.run_in_threadpool` — not on the event loop. |
| 12 | `test_session_construction_failure_is_swallowed` (review fix) | If `Database(db=SessionLocal())` itself raises (engine closed / pool teardown), failure is logged, helper returns None. |
| 13 | `test_stack_trace_is_real_for_fn_exception` (review fix) | `stack_trace` in the logged row contains the fn's real frames, not `"NoneType: None"`. |
| 14 | `test_stack_trace_is_not_nonetype_for_fabricated_error` (review fix) | SessionLocal-None path fabricates a RuntimeError without raising it; `traceback.format_exception(...)` still produces a useful single-line trace instead of `"NoneType: None"`. |

## Adversarial review findings (all fixed before commit)

1. **`traceback.format_exc()` returns `"NoneType: None"` for fabricated exceptions.**
   The SessionLocal-is-None path constructs a `RuntimeError` but never
   raises it — `format_exc()` reads `sys.exc_info()` which is empty,
   producing a useless stored trace. **Fix:** use
   `traceback.format_exception(type(error), error, error.__traceback__)`
   on the error object itself. Covered by test #14.

2. **Session construction failure bubbles to the caller.**
   `Database(db=SessionLocal())` can raise (engine closed during
   graceful shutdown, pool exhausted, stale config) — the original
   implementation let that exception escape, violating the
   fire-and-forget contract. **Fix:** wrap construction in its own
   try/except and log the failure instead. Covered by test #12.

No action items deferred — both findings fixed, tests added, re-review
clean.

## Manual QA (runtime sanity)

Not applicable — this is a pure foundations helper with no user-facing
surface. Adoption in D-01..D-13 is where runtime-path QA will happen
(per-domain QA walkthroughs will include the notification-dispatch path
through this helper).

## Risks known to oncall

- **`error_logs` volume.** If a sync notification helper starts
  failing persistently (e.g., Firebase SDK outage), rows will
  accumulate under `service='push_notifications'`. This is
  intentional — oncall triage queries:
  ```bash
  python services/api/scripts/audit_errors.py --service push_notifications --window 1h
  python services/api/scripts/audit_errors.py --drill push_notifications: --window 1h
  ```
  No new alerting required — the existing push-stack monitors key off
  the same service label.

- **`ErrorLog.error_code` not set.** This column exists on the ORM
  model but we don't populate it — we have a class name (`error_type`)
  and a message, which is sufficient for `audit_errors.py` triage.
  `error_code` is reserved for APIException codes in the codebase, not
  applicable here.

## Done

- [x] `nx run utils:lint` green.
- [x] `nx run utils:test` — 14/14 pass.
- [x] `nx run api:lint` green.
- [x] `nx run api:test` green (not directly testing this module — the
      full suite must stay green).
- [x] `sprint-status.yaml` flipped `aam-foundations-notify-threadpool-helper: backlog → done`.
- [x] Adversarial review complete; all findings fixed in-loop.
- [x] Atomic commit — only story-scoped files touched.
