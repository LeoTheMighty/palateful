"""Tests for utils.services.redis_client.

Fail-open semantics are the core contract: `get_redis()` returns None
on any failure path, `safe_get` returns None on any error, `safe_set`
returns False. No caller ever sees an exception.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from utils.services import redis_client


@pytest.fixture(autouse=True)
def reset_module_state():
    """Drop module-global client between tests."""
    redis_client.reset_redis_cache()
    yield
    redis_client.reset_redis_cache()


class TestGetRedisInit:
    async def test_redis_url_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        result = await redis_client.get_redis()
        assert result is None

    async def test_connect_refused_returns_none(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://nonexistent:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(
            side_effect=RedisConnectionError("connect refused")
        )
        with patch.object(redis_client, "Redis", return_value=fake_client):
            result = await redis_client.get_redis()
        assert result is None

    async def test_op_timeout_on_ping_returns_none(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://flaky:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(
            side_effect=RedisTimeoutError("ping timed out")
        )
        with patch.object(redis_client, "Redis", return_value=fake_client):
            result = await redis_client.get_redis()
        assert result is None

    async def test_oserror_on_pool_returns_none(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        with patch.object(
            redis_client.ConnectionPool,
            "from_url",
            side_effect=OSError("dns failure"),
        ):
            result = await redis_client.get_redis()
        assert result is None

    async def test_happy_path_returns_client(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(return_value=True)
        with patch.object(redis_client, "Redis", return_value=fake_client):
            result = await redis_client.get_redis()
        assert result is fake_client

    async def test_client_cached_across_calls(self, monkeypatch):
        """Second call returns same client without re-pinging."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(return_value=True)
        with patch.object(redis_client, "Redis", return_value=fake_client):
            first = await redis_client.get_redis()
            second = await redis_client.get_redis()
        assert first is second
        # Ping only called once across the two get_redis() calls.
        fake_client.ping.assert_awaited_once()

    async def test_none_result_cached(self, monkeypatch):
        """Once we decide Redis is unavailable, stay decided — don't re-try
        every request (would be a self-DoS on a flapping Redis)."""
        monkeypatch.setenv("REDIS_URL", "redis://nonexistent:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(
            side_effect=RedisConnectionError("gone")
        )
        with patch.object(redis_client, "Redis", return_value=fake_client):
            first = await redis_client.get_redis()
            second = await redis_client.get_redis()
        assert first is None
        assert second is None
        # Second call hit the cache, didn't try to ping again.
        fake_client.ping.assert_awaited_once()


class TestSafeGet:
    async def test_returns_none_when_redis_unavailable(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        result = await redis_client.safe_get("k")
        assert result is None

    async def test_returns_value_on_hit(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(return_value=True)
        fake_client.get = AsyncMock(return_value="cached-value")
        with patch.object(redis_client, "Redis", return_value=fake_client):
            result = await redis_client.safe_get("k")
        assert result == "cached-value"

    async def test_returns_none_on_connection_error(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(return_value=True)
        fake_client.get = AsyncMock(
            side_effect=RedisConnectionError("dropped")
        )
        with patch.object(redis_client, "Redis", return_value=fake_client):
            result = await redis_client.safe_get("k")
        assert result is None

    async def test_returns_none_on_timeout(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(return_value=True)
        fake_client.get = AsyncMock(
            side_effect=RedisTimeoutError("too slow")
        )
        with patch.object(redis_client, "Redis", return_value=fake_client):
            result = await redis_client.safe_get("k")
        assert result is None


class TestSafeSet:
    async def test_returns_false_when_redis_unavailable(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        ok = await redis_client.safe_set("k", "v", ex=60)
        assert ok is False

    async def test_returns_true_on_happy_path(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(return_value=True)
        fake_client.set = AsyncMock(return_value=True)
        with patch.object(redis_client, "Redis", return_value=fake_client):
            ok = await redis_client.safe_set("k", "v", ex=60)
        assert ok is True
        fake_client.set.assert_awaited_once_with("k", "v", ex=60)

    async def test_returns_false_on_connection_error(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        fake_client = MagicMock()
        fake_client.ping = AsyncMock(return_value=True)
        fake_client.set = AsyncMock(side_effect=RedisConnectionError("down"))
        with patch.object(redis_client, "Redis", return_value=fake_client):
            ok = await redis_client.safe_set("k", "v", ex=60)
        assert ok is False
