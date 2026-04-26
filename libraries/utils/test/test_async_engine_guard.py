"""Regression: utils.services.database stays importable when asyncpg is
missing and ASYNC_DATABASE_URL resolves (worker-async-cleanup-3).

Pre-cleanup, importing this module while DB_HOST/USERNAME/PASSWORD/NAME
were set (i.e. ASYNC_DATABASE_URL non-empty) but asyncpg wasn't in the
venv crashed the host process at module load — SQLAlchemy eager-loads
the asyncpg dialect inside `create_async_engine`. We caught the worker
this way in commit 9704240; the guard added in
`libraries/utils/utils/services/database.py` converts the crash into a
logged warning + sync-only Database surface so the next service that
picks up `utils.services.database` doesn't repeat the prod incident.
"""

from __future__ import annotations

import logging
import sys

import pytest

from utils.services.database import _build_async_engine_and_session


def test_returns_none_pair_when_async_url_empty():
    """No URL → both surfaces are None. Keeps services that don't run
    async (worker test image, parser, scripts) cheap and predictable."""
    assert _build_async_engine_and_session(None) == (None, None)
    assert _build_async_engine_and_session("") == (None, None)


def test_returns_none_pair_and_warns_when_asyncpg_missing(monkeypatch, caplog):
    """ASYNC_DATABASE_URL resolves, asyncpg unavailable → log warning,
    return (None, None) so callers fall back to the sync Database surface
    instead of crashing the host process at import time."""
    # Block `import asyncpg` for the duration of the test. Setting a
    # module entry to None makes Python raise ImportError on import.
    monkeypatch.setitem(sys.modules, "asyncpg", None)

    caplog.set_level(logging.WARNING, logger="utils.services.database")

    engine, session_factory = _build_async_engine_and_session(
        "postgresql+asyncpg://u:p@unreachable.test:5432/d"
    )

    assert engine is None, f"engine should be None when asyncpg missing, got {engine!r}"
    assert session_factory is None, (
        f"session_factory should be None when asyncpg missing, got {session_factory!r}"
    )

    warnings = [
        rec for rec in caplog.records
        if rec.levelno == logging.WARNING and rec.name == "utils.services.database"
    ]
    assert warnings, "Expected a warning from utils.services.database; got none"
    assert any("asyncpg not installed" in rec.message for rec in warnings), (
        f"Expected the asyncpg-missing warning; got: {[r.message for r in warnings]!r}"
    )


def test_returns_real_engine_when_asyncpg_present():
    """Sanity: when asyncpg is available the guard falls through and the
    async engine gets built normally. Prevents a regression where the
    guard accidentally short-circuits the happy path.

    Skipped in the libraries/utils venv (asyncpg not pinned there); runs
    in services/api / services/worker venvs where asyncpg IS pinned and
    these tests are also exercised."""
    pytest.importorskip("asyncpg")

    engine, session_factory = _build_async_engine_and_session(
        "postgresql+asyncpg://u:p@unreachable.test:5432/d"
    )

    assert engine is not None
    assert session_factory is not None
