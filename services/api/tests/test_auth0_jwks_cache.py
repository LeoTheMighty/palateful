"""Tests for utils.services.auth0 JWKS caching behavior (pim-5).

Covers:
- Three-tier read-through (in-memory → Redis → Auth0)
- Stale-but-present hit triggers background refresh, still serves the
  stale value
- Single-flight lock prevents concurrent Auth0 round-trips from a
  single task
- Fail-open when Redis is unavailable
- Redis-only hit hydrates in-memory
- Corrupt Redis value treated as a miss
"""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.services import auth0, redis_client


@pytest.fixture(autouse=True)
def _reset_state():
    auth0.clear_auth0_verifier_cache()
    redis_client.reset_redis_cache()
    yield
    auth0.clear_auth0_verifier_cache()
    redis_client.reset_redis_cache()


def _make_verifier() -> auth0.Auth0Verifier:
    return auth0.Auth0Verifier(domain="example.auth0.com", audience="aud")


_SAMPLE_JWKS = {
    "keys": [
        {"kid": "abc", "kty": "RSA", "use": "sig", "n": "x", "e": "AQAB"}
    ]
}


class TestInMemoryFreshHit:
    async def test_serves_from_memory_when_fresh(self):
        v = _make_verifier()
        v._jwks = _SAMPLE_JWKS
        v._jwks_fetched_at = time.time()  # just now
        with patch.object(v, "_fetch_from_auth0", new=AsyncMock()) as fetcher:
            result = await v._get_jwks()
        assert result == _SAMPLE_JWKS
        fetcher.assert_not_awaited()


class TestStaleButPresent:
    async def test_serves_stale_and_triggers_background_refresh(self):
        v = _make_verifier()
        v._jwks = _SAMPLE_JWKS
        # Fetched 55 min ago — past soft TTL (50 min), before hard (60 min).
        v._jwks_fetched_at = time.time() - 55 * 60
        fresh = {"keys": [{"kid": "new", "kty": "RSA", "use": "sig",
                           "n": "y", "e": "AQAB"}]}

        with patch.object(
            v, "_fetch_from_auth0", new=AsyncMock(return_value=fresh)
        ):
            # First call: serves stale, schedules background refresh.
            result = await v._get_jwks()
            assert result == _SAMPLE_JWKS

            # Await outstanding refresh tasks. The event loop schedules
            # the bg task via loop.create_task; we need to let it run.
            if v._bg_refresh_task is not None:
                await v._bg_refresh_task

        # After the refresh, in-memory is the fresh blob.
        assert v._jwks == fresh
        assert v._jwks_fetched_at > time.time() - 10


class TestHardTTLExpiry:
    async def test_memory_past_hard_ttl_triggers_fetch(self):
        v = _make_verifier()
        v._jwks = _SAMPLE_JWKS
        v._jwks_fetched_at = time.time() - 2 * 3600  # 2h ago — past hard
        fresh = {"keys": [{"kid": "fresh", "kty": "RSA", "use": "sig",
                           "n": "z", "e": "AQAB"}]}

        # Redis unavailable → fall through to fetch.
        with (
            patch.object(auth0, "safe_get",
                         new=AsyncMock(return_value=None)),
            patch.object(auth0, "safe_set",
                         new=AsyncMock(return_value=True)),
            patch.object(v, "_fetch_from_auth0",
                         new=AsyncMock(return_value=fresh)) as fetcher,
        ):
            result = await v._get_jwks()

        assert result == fresh
        fetcher.assert_awaited_once()


class TestRedisHit:
    async def test_redis_hit_hydrates_memory(self):
        v = _make_verifier()
        # In-memory empty.
        fetched_at = time.time() - 300  # 5 min ago — fresh
        redis_blob = json.dumps({"jwks": _SAMPLE_JWKS, "fetched_at": fetched_at})

        with (
            patch.object(auth0, "safe_get",
                         new=AsyncMock(return_value=redis_blob)),
            patch.object(v, "_fetch_from_auth0",
                         new=AsyncMock()) as fetcher,
        ):
            result = await v._get_jwks()

        assert result == _SAMPLE_JWKS
        assert v._jwks == _SAMPLE_JWKS
        assert abs(v._jwks_fetched_at - fetched_at) < 0.01
        fetcher.assert_not_awaited()

    async def test_redis_hit_stale_but_present_serves_and_refreshes(self):
        v = _make_verifier()
        fetched_at = time.time() - 55 * 60  # past soft TTL
        redis_blob = json.dumps({"jwks": _SAMPLE_JWKS, "fetched_at": fetched_at})
        fresh = {"keys": [{"kid": "new", "kty": "RSA", "use": "sig",
                           "n": "a", "e": "AQAB"}]}

        with (
            patch.object(auth0, "safe_get",
                         new=AsyncMock(return_value=redis_blob)),
            patch.object(auth0, "safe_set",
                         new=AsyncMock(return_value=True)),
            patch.object(v, "_fetch_from_auth0",
                         new=AsyncMock(return_value=fresh)),
        ):
            result = await v._get_jwks()
            # Stale serve returns the cached value, not the fresh one yet.
            assert result == _SAMPLE_JWKS
            if v._bg_refresh_task is not None:
                await v._bg_refresh_task

        # After the background refresh, in-memory holds the fresh blob.
        assert v._jwks == fresh

    async def test_redis_past_hard_ttl_ignored(self):
        v = _make_verifier()
        fetched_at = time.time() - 2 * 3600  # past hard TTL
        redis_blob = json.dumps({"jwks": _SAMPLE_JWKS, "fetched_at": fetched_at})
        fresh = {"keys": [{"kid": "z"}]}

        with (
            patch.object(auth0, "safe_get",
                         new=AsyncMock(return_value=redis_blob)),
            patch.object(auth0, "safe_set",
                         new=AsyncMock(return_value=True)),
            patch.object(v, "_fetch_from_auth0",
                         new=AsyncMock(return_value=fresh)) as fetcher,
        ):
            result = await v._get_jwks()

        assert result == fresh
        fetcher.assert_awaited_once()

    async def test_corrupt_redis_value_treated_as_miss(self):
        v = _make_verifier()
        fresh = {"keys": [{"kid": "ok"}]}
        with (
            patch.object(auth0, "safe_get",
                         new=AsyncMock(return_value="{ not valid json")),
            patch.object(auth0, "safe_set",
                         new=AsyncMock(return_value=True)),
            patch.object(v, "_fetch_from_auth0",
                         new=AsyncMock(return_value=fresh)) as fetcher,
        ):
            result = await v._get_jwks()
        assert result == fresh
        fetcher.assert_awaited_once()


class TestSingleFlight:
    async def test_concurrent_cold_fetches_dedupe(self):
        """5 concurrent cold _get_jwks() calls should hit Auth0 ONCE."""
        v = _make_verifier()
        fetch_count = 0

        async def slow_fetch():
            nonlocal fetch_count
            fetch_count += 1
            # Small sleep simulates network round-trip; concurrent
            # callers should wait on the lock while the first is in-flight.
            await asyncio.sleep(0.05)
            return _SAMPLE_JWKS

        with (
            patch.object(auth0, "safe_get",
                         new=AsyncMock(return_value=None)),
            patch.object(auth0, "safe_set",
                         new=AsyncMock(return_value=True)),
            patch.object(v, "_fetch_from_auth0", new=slow_fetch),
        ):
            results = await asyncio.gather(
                *(v._get_jwks() for _ in range(5))
            )

        assert all(r == _SAMPLE_JWKS for r in results)
        assert fetch_count == 1


class TestFailOpenWhenRedisDown:
    async def test_redis_unavailable_fetches_from_auth0(self):
        v = _make_verifier()
        fresh = {"keys": [{"kid": "ok"}]}
        with (
            # safe_get returns None (Redis unreachable)
            patch.object(auth0, "safe_get",
                         new=AsyncMock(return_value=None)),
            # safe_set returns False (write didn't land)
            patch.object(auth0, "safe_set",
                         new=AsyncMock(return_value=False)),
            patch.object(v, "_fetch_from_auth0",
                         new=AsyncMock(return_value=fresh)),
        ):
            result = await v._get_jwks()

        assert result == fresh
        # In-memory hydrated for subsequent requests in this task.
        assert v._jwks == fresh


class TestClearCache:
    async def test_clear_drops_in_memory_tier(self):
        v = _make_verifier()
        v._jwks = _SAMPLE_JWKS
        v._jwks_fetched_at = time.time()
        v.clear_jwks_cache()
        assert v._jwks is None
        assert v._jwks_fetched_at == 0.0

    async def test_clear_cancels_inflight_bg_refresh(self):
        v = _make_verifier()

        async def slow():
            await asyncio.sleep(10)
            return _SAMPLE_JWKS

        # Prime state so _schedule_background_refresh sets the bg task.
        v._jwks = _SAMPLE_JWKS
        v._jwks_fetched_at = time.time() - 55 * 60
        with (
            patch.object(auth0, "safe_set",
                         new=AsyncMock(return_value=True)),
            patch.object(v, "_fetch_from_auth0", new=slow),
        ):
            await v._get_jwks()

        assert v._bg_refresh_task is not None
        assert not v._bg_refresh_task.done()
        # Hold onto the reference before clear_jwks_cache() nulls it.
        pending = v._bg_refresh_task

        v.clear_jwks_cache()
        # cancel() is cooperative — await the captured task so pytest
        # doesn't complain about unhandled tasks at teardown.
        try:
            await pending
        except asyncio.CancelledError:
            pass
        assert pending.cancelled()
