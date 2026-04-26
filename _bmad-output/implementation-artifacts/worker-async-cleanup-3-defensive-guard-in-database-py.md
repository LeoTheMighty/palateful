# worker-async-cleanup-3 — defensive guard in `database.py`

**Epic:** `epic-worker-async-engine-cleanup`
**Status:** done
**Parent ACs:** epic-worker-async-engine-cleanup § Story 3

## Scope

Convert the unconditional `create_async_engine(...)` call at the top of
`libraries/utils/utils/services/database.py` into a guarded build path
that probe-imports `asyncpg` first. Without the guard, the next service
to acquire a `utils = {path = ...}` dep AND a prod runtime with
`DB_HOST`/`DB_USERNAME`/`DB_PASSWORD`/`DB_NAME` set will repeat the
2026-04-25 worker incident — SQLAlchemy eager-loads the asyncpg dialect
inside `create_async_engine`, the `__import__("asyncpg")` raises, and
the host process dies at module load (celery / uvicorn / batch entry
point all hit this on first import).

Story 1 confirmed nothing in the current tree trips on this; Story 3 is
the systemic safety net.

## Why guard instead of pin everywhere

Pinning asyncpg in every service that *might* one day import
`utils.services.database` is dead weight — asyncpg has a C extension and
inflates the venv / container. The guard lets services that don't need
async I/O stay slim while keeping the ones that do (api, worker, eval,
migrator) on the same code path. The cost is one extra `import asyncpg`
at module load when the env actually wants async, which is microseconds.

## Acceptance Criteria (from epic)

- [x] `if ASYNC_DATABASE_URL:` branch wraps `create_async_engine` in a
      `try: import asyncpg / except ImportError` so a missing dep
      becomes a logged warning, not a crash.
- [x] When the import fails, `async_db_engine` and `AsyncSessionLocal`
      are both `None` so callers can fall back to the sync `Database`
      surface.
- [x] When the import succeeds, the async engine is built with the
      same parameters as before (no behavioral change for callers that
      already work).
- [x] `pytest libraries/utils/` is green (modulo pre-existing
      `test_freeform_units_seed.py` / `test_freeform_unit_aliases_seed.py`
      failures that fail without `alembic` in the venv — these fail on
      `main` already, unrelated to this story).
- [x] Sync `Database` public surface is unchanged
      (`test_database_api_frozen.py` stays green).

## Implementation

### Files touched

- `libraries/utils/utils/services/database.py` — extracted the async
  engine-build path into `_build_async_engine_and_session(async_url)`.
  The function:
  1. Returns `(None, None)` immediately if `async_url` is falsy.
  2. Probe-imports `asyncpg`; on `ImportError` logs a warning that
     names the missing dep and returns `(None, None)` — sync surface
     stays usable.
  3. Otherwise builds the engine + session_factory with the same
     pool/connect_args parameters as before and returns the pair.
  Module-level assignment becomes one line:
  `async_db_engine, AsyncSessionLocal = _build_async_engine_and_session(ASYNC_DATABASE_URL)`.
- `libraries/utils/test/test_async_engine_guard.py` — three tests:
  1. **Empty URL → `(None, None)`**: documents the cheap path
     used by the worker test image and any future service whose env
     genuinely doesn't wire DB_*.
  2. **Missing asyncpg → `(None, None)` + warning**: simulates the
     prod-incident shape by patching `sys.modules["asyncpg"] = None`,
     calls the function with a postgresql+asyncpg URL, and asserts the
     engine is None AND a warning was logged from the
     `utils.services.database` logger with the diagnostic substring.
  3. **asyncpg present → real engine**: `pytest.importorskip("asyncpg")`
     so the test skips in the libraries/utils venv (no asyncpg pinned)
     but runs in the api / worker venvs where asyncpg IS present.
     Verifies the guard doesn't accidentally short-circuit the happy
     path.

### Why a function instead of inline try/except

The original epic snippet shows an inline `try/except ImportError`
around `create_async_engine`. We extracted it into
`_build_async_engine_and_session` because:

1. **Testability without subprocess**: testing the inline form requires
   forcing a fresh interpreter to re-execute the module body. Function
   form lets pytest call the function directly with monkeypatched
   `sys.modules` — clean unit test, no subprocess cost, no risk of
   leaking module state into other tests.
2. **Symmetric to the sync path future**: if we ever need a similar
   guard for psycopg (currently the sync path's only DBAPI), pulling
   that into `_build_sync_engine_and_session` keeps the module's two
   engine-build paths shaped identically.

The behavioral contract is otherwise identical to the epic's snippet.

## Test results

```
$ poetry run pytest libraries/utils/test/test_async_engine_guard.py -v
test_returns_none_pair_when_async_url_empty            PASSED
test_returns_none_pair_and_warns_when_asyncpg_missing  PASSED
test_returns_real_engine_when_asyncpg_present          SKIPPED  (utils venv)
                                                       PASSED   (api venv — asyncpg installed)
```

Full suite (libraries/utils): **589 passed, 1 skipped, 12 baseline
failures** (all in `test_freeform_unit_aliases_seed.py` /
`test_freeform_units_seed.py`, all due to `ModuleNotFoundError: alembic`
which fails identically on `origin/main` — pre-existing, unrelated to
this story).

## QA Checklist

- [x] `_build_async_engine_and_session(None)` returns `(None, None)`.
- [x] `_build_async_engine_and_session("")` returns `(None, None)`.
- [x] With `sys.modules["asyncpg"] = None`,
      `_build_async_engine_and_session("postgresql+asyncpg://...")`
      returns `(None, None)` AND logs a warning containing
      `"asyncpg not installed"`.
- [x] With asyncpg available,
      `_build_async_engine_and_session("postgresql+asyncpg://...")`
      returns a real `AsyncEngine` + `async_sessionmaker`.
- [x] `Database` public surface unchanged (frozen-API test green).
- [x] `npx nx run utils:lint` clean.
- [x] `git diff` of `database.py` is exactly the guard refactor —
      no incidental cleanup, no behavior changes outside the async
      block.

## File List

- Modified: `libraries/utils/utils/services/database.py`
- Created: `libraries/utils/test/test_async_engine_guard.py`
- Created: `_bmad-output/implementation-artifacts/worker-async-cleanup-3-defensive-guard-in-database-py.md`
- Created: `_bmad-output/implementation-artifacts/worker-async-cleanup-3-qa-walkthrough.md`
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml`
