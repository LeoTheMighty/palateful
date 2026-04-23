"""Unit tests for AsyncAdvisoryLock (aam-2)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.services.async_advisory_lock import AsyncAdvisoryLock
from utils.services.advisory_lock import AdvisoryLock


def test_hash_key_matches_sync_advisory_lock():
    """Sync and async locks on the same string key MUST produce the same
    64-bit hash, otherwise a sync caller and an async caller contending
    for the same logical resource would lock independently and a
    find_or_create_by race becomes possible."""
    assert AsyncAdvisoryLock.hash_key("Recipe_owner_id_abc") == AdvisoryLock.hash_key(
        "Recipe_owner_id_abc"
    )


def _fake_async_engine():
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.commit = AsyncMock()
    conn.rollback = AsyncMock()
    conn.close = AsyncMock()
    engine = MagicMock()
    engine.connect = AsyncMock(return_value=conn)
    return engine, conn


async def test_enter_acquires_lock_and_exit_commits_and_unlocks():
    engine, conn = _fake_async_engine()
    lock = AsyncAdvisoryLock(engine, "key")
    async with lock:
        pass
    # Should have: connect, acquire, commit, unlock, close.
    assert conn.execute.await_count == 2  # acquire + unlock
    conn.commit.assert_awaited_once()
    conn.close.assert_awaited_once()


async def test_exit_rolls_back_when_exception_raised_inside_block():
    engine, conn = _fake_async_engine()
    lock = AsyncAdvisoryLock(engine, "key")
    with pytest.raises(RuntimeError):
        async with lock:
            raise RuntimeError("boom")
    conn.rollback.assert_awaited_once()
    # Lock must still be released — connection still closed.
    conn.close.assert_awaited_once()
