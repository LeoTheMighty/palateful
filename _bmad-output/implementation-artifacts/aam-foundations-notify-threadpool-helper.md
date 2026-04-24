# aam-foundations-notify-threadpool-helper — `notify_via_threadpool` helper

**Epic:** `epic-api-async-migration`
**Chunk:** Foundations CHUNK-F1 (per `_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md`)
**Status:** review
**Serial gate:** yes — every domain chunk (D-01..D-13) waits on this to land before they can convert their notification fan-out cleanly.

## Why

After Phase 0 (commit `2243928`) flipped 150 sync-bodied `async def`
handlers to `def`, the fix that follows (each `aam-NN-*` domain chunk)
converts endpoints to `AsyncEndpoint`. The one bridge every such
endpoint needs is "how do I call the existing sync
`notify_*` / `create_activity` / `send_to_user` helper from an async
execute method?" — the helpers still take `database: Database` (sync
session) and aren't going async in Phase 1.

Without a shared helper, every domain would grow a bespoke
`def _sync_side_effect(): sync_db = Database(db=SessionLocal()); try:
notify_X(...); finally: sync_db.close()` block, each with slightly
different exception handling and its own logger. That's 13
near-identical blocks a future grep-and-delete pass (CHUNK-C4) would
have to locate and unify. Ship one helper once, use it everywhere, and
CHUNK-C4 has a single callsite to retire.

## Scope — files this story touches

- **NEW** `libraries/utils/utils/services/notifications_bridge.py` — the
  `notify_via_threadpool` helper.
- **NEW** `libraries/utils/test/test_notifications_bridge.py` — unit
  tests (success path, exception path, session-closed invariant,
  reserved-kwarg guard).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — flip
  `aam-foundations-notify-threadpool-helper: backlog → done`.
- `_bmad-output/implementation-artifacts/aam-foundations-notify-threadpool-helper.md`
  (this file — the story spec).
- `_bmad-output/implementation-artifacts/aam-foundations-notify-threadpool-helper-qa-walkthrough.md`
  (QA checklist).

### Out of scope — deliberate deferrals

- **No domain chunk touched.** F1 ships only the helper + its tests. D-01..D-13
  adopt it in their own commits.
- **No `__init__.py` re-export.** `libraries/utils/utils/services/__init__.py`
  is empty today; all other sibling helpers are imported directly
  (`from utils.services.X import Y`). Adding a re-export would violate
  the project invariant "no new abstractions". The phase-1 dev-snippet
  doc's mention of "services/__init__.py (export)" is stale — callers
  will `from utils.services.notifications_bridge import notify_via_threadpool`
  directly. Recorded here so reviewers don't flag its absence.
- **Test file location.** The phase-1 dev-snippet doc places the test at
  `services/api/tests/test_notifications_bridge.py`. We deviate — all
  four sibling notification helpers are tested from `libraries/utils/test/`
  (test_push_notification.py, test_import_notifications.py,
  test_meal_event_notifications.py, test_notification_copy.py). The
  helper is pure utils, no api wiring, so the utils suite is the right
  home. Keeps api coverage focused on api-owned code.

## Contract

```python
async def notify_via_threadpool(fn, *args, **kwargs) -> None:
    """Run a sync notification helper on a fresh sync Database inside the threadpool.

    The helper:
      1. Creates a fresh `Database(db=SessionLocal())` ON THE THREADPOOL
         THREAD (not the event loop, so the sync pool is not touched
         from async code).
      2. Calls `fn(*args, database=<that session>, **kwargs)`.
      3. Closes the session in a `finally` block — the session is released
         even if `fn` raises.
      4. Swallows any exception from `fn` (notifications are fire-and-forget);
         logs the failure to `error_logs` with `service='push_notifications'`
         for triage via `bin/prod-logs` / `audit_errors.py`.
      5. Returns `None`. Callers must not rely on the notification's
         return value (single call site where a return value would be
         meaningful is `notify_meal_event_reminder` → its `{sent, suppressed,
         attempted}` dict — those callsites call it directly from async
         scheduler tasks, not via this bridge).

    `fn` MUST accept `database: Database` as a keyword argument. Callers
    MUST NOT pass `database` themselves — the helper injects it and will
    raise `TypeError` up-front if the caller does.
    """
```

## Acceptance criteria

1. **Helper exists.** `libraries/utils/utils/services/notifications_bridge.py`
   exports `notify_via_threadpool(fn, *args, **kwargs)` matching the
   contract above.
2. **Threadpool dispatch.** The sync callback (including
   `Database(db=SessionLocal())` construction) runs on the threadpool
   thread via `fastapi.concurrency.run_in_threadpool`, never on the
   event loop.
3. **Session always closed.** `database.close()` runs in `finally` —
   covered by a test that asserts `close()` is called after `fn` raises.
4. **Exception swallowed + logged.** An exception raised by `fn` does NOT
   propagate out of `notify_via_threadpool`; an `ErrorLog` row is
   written with `service='push_notifications'`, `error_type` = the
   exception's class name, and `error_message` containing the fn name
   and str(exception) (truncated to 4000 chars to match
   `AsyncEndpoint._log_error_to_db`).
5. **Reserved-kwarg guard.** Passing `database=...` in kwargs raises
   `TypeError` synchronously (before any threadpool hop) — tested.
6. **Fallback to main engine.** When `ErrorLogSessionLocal` is None
   (workers, scripts), the error-log write falls back to `Database()`
   using the default engine — tested.
7. **Graceful when SessionLocal is None.** If `SessionLocal` itself is
   None (import-safe environments), the helper logs a failure row with
   `error_type='RuntimeError'` and returns without calling `fn` —
   tested.
8. **Error-log write failures are never re-raised.** A failure inside
   the failure-logger is swallowed (best-effort) and emitted via
   `logger.exception`. Matches `PushNotificationService._log_send_failure`
   precedent.
9. **Test coverage** passes under `libraries/utils` pytest run; `nx run
   utils:lint` and `nx run api:lint` both pass. `nx run api:test` also
   passes (api doesn't directly test this module but the full suite
   must stay green).
10. **Sprint-status flipped** `aam-foundations-notify-threadpool-helper:
    backlog → done`.

## Tests (test file: `libraries/utils/test/test_notifications_bridge.py`)

| # | Test | Asserts |
|---|---|---|
| 1 | `test_happy_path_injects_database_kwarg` | `fn` is called with the injected `database=` matching the patched `Database` instance; positional args and non-reserved kwargs forwarded as-is; returns `None`. |
| 2 | `test_session_closed_on_success` | `database.close()` is called exactly once after a successful `fn` call. |
| 3 | `test_session_closed_on_exception` | `database.close()` is called even when `fn` raises; helper does NOT re-raise. |
| 4 | `test_exception_logs_error_row_with_push_service` | On `fn` raising, one `ErrorLog` row is inserted with `service='push_notifications'`, `error_type=` the exception class, and `error_message` containing the fn name + str(exc). |
| 5 | `test_reserved_database_kwarg_raises_typeerror` | Passing `database=<anything>` as a kwarg raises `TypeError` synchronously; threadpool never entered. |
| 6 | `test_error_log_uses_error_log_engine_when_available` | When `ErrorLogSessionLocal` is non-None, the error-log `Database` is constructed with that sub-pool session; when it's None, falls back to `Database()` with main engine. |
| 7 | `test_session_local_missing_logs_runtime_error` | With `SessionLocal = None`, `fn` is never called; an `ErrorLog` row with `error_type='RuntimeError'` and message mentioning SessionLocal is written. |
| 8 | `test_error_log_write_failure_is_swallowed` | If `ErrorLog` insert itself raises, helper returns normally (no exception out). |

## Adoption note for domain chunks (D-01..D-13)

Each domain chunk converts callsites of existing sync notification helpers
from:

```python
def _sync_side_effect():
    sync_db = Database(db=SessionLocal())
    try:
        notify_book_shared(recipe_book_id=..., database=sync_db)
    finally:
        sync_db.close()
await run_in_threadpool(_sync_side_effect)
```

to:

```python
await notify_via_threadpool(
    notify_book_shared,
    recipe_book_id=...,
)
```

The sync helpers (`notify_import_needs_review`, `notify_book_shared`,
`notify_meal_event_updated`, `notify_shopping_deadline_reminder`, ...)
already accept `database` as their first positional arg, which Python
allows to be passed as the keyword `database=...`. No changes to the
helpers themselves — the bridge just standardises the dispatch.

## Risks & mitigations

- **Risk:** helper starts mid-call while `SessionLocal` is being
  re-initialised (unlikely — only happens in test teardown).
  **Mitigation:** snapshot `SessionLocal` on the threadpool thread; the
  single reference is captured in the `_invoke_sync` closure at
  dispatch time. If `None`, we log and return (AC #7).
- **Risk:** a future caller passes an async callable by mistake.
  **Mitigation:** `run_in_threadpool` forwards the coroutine object to
  the thread; calling it there returns an un-awaited coroutine. Python
  emits `RuntimeWarning: coroutine was never awaited`. Not catastrophic
  but noisy — documented as a caller-side constraint. An explicit
  `iscoroutinefunction(fn)` guard is out of scope for F1 (premature
  abstraction — no async notification helpers exist yet).
- **Risk:** the error-log write reaches `push_notifications` dashboards
  used by oncall. **Mitigation:** this is the desired behaviour — the
  row should be surfaceable via `audit_errors.py --service
  push_notifications`, which is already the triage path for the push
  stack.

## Definition of done

- [x] Helper implemented and tested (unit tests 1–8 above green).
- [x] `nx run utils:lint`, `nx run api:lint`, `nx run utils:test`,
      `nx run api:test` all green.
- [x] Sprint-status entry flipped `backlog → done`.
- [x] QA walkthrough file present
      (`aam-foundations-notify-threadpool-helper-qa-walkthrough.md`).
- [x] One atomic commit per story loop invariant — no unrelated
      file-list entries.
