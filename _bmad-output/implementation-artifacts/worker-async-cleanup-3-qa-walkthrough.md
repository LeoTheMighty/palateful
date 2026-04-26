# worker-async-cleanup-3 — QA walkthrough

Three checks. No DB, no AWS — all local, ~2 minutes end-to-end.

## 1. Guard tests pass in the libraries/utils venv

```
cd libraries/utils
poetry run pytest test/test_async_engine_guard.py --no-cov -v
```

**Pass:** `2 passed, 1 skipped` — the empty-URL and missing-asyncpg
cases run; the happy-path case skips because asyncpg isn't pinned in
this venv (`pytest.importorskip("asyncpg")`).
**Fail:** any failure other than the expected skip — the guard is
broken, do not merge.

## 2. Guard tests pass in the api venv (covers the happy path)

```
cd services/api
poetry run pytest /absolute/path/to/libraries/utils/test/test_async_engine_guard.py --no-cov -v
```

**Pass:** `3 passed` — the happy-path test runs because
`services/api/pyproject.toml` pins asyncpg.
**Fail:** the happy-path test errors — the function refactor broke the
non-fallback path (most likely a typo in the kwargs passed to
`create_async_engine` or `async_sessionmaker`).

## 3. Frozen sync API still locked

```
cd libraries/utils
poetry run pytest test/test_database_api_frozen.py --no-cov -v
```

**Pass:** all asserts green — sync `Database` public methods + their
signatures are unchanged. The story should not have shifted them.
**Fail:** the refactor accidentally added/removed/renamed a sync
method or changed a signature; revert and tighten the change to the
async block only.

## 4. Smoke: services/api and services/worker still importable

```
cd services/api
poetry run python -c "from utils.services.database import async_db_engine, AsyncSessionLocal; print('api OK')"
cd ../worker
poetry run python -c "from utils.services.database import async_db_engine, AsyncSessionLocal; print('worker OK')"
```

**Pass:** both print `OK`. (These venvs have asyncpg pinned, so the
async surface should be available — though `async_db_engine` itself
will be `None` here because `DATABASE_URL` isn't set in the shell.)
**Fail:** `ImportError` from `utils.services.database` — the guard
broke the import for services that already pin asyncpg, which is the
opposite of what this story is supposed to do.
