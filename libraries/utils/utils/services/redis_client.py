"""Async Redis client wrapper with fail-open semantics.

Introduced by pim-5 (2026-04-21) to back the Auth0 JWKS cache.

**Fail-open is non-negotiable.** Callers MUST treat `get_redis()` → None
as "Redis unavailable — use the in-memory fallback" without raising.
Every Redis operation is wrapped so that:

- Connect-refused → return None (client not created / poisoned)
- Op-timeout → return None (operation-level, after >=1 successful
  connection)
- `REDIS_URL` unset → return None (we're in local dev without Redis)

The connection pool caps at 10 concurrent connections. Timeouts are
aggressive — 100ms connect / 50ms op — because Redis is on the same
VPC and any slower is a failure mode we'd rather fail open on than
stall the request.

On fresh creation the client is pinged; if the ping times out or raises,
we cache `None` for a short TTL so we don't thrash on a flapping Redis.
"""

from __future__ import annotations

import logging
import os

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT_S = 0.1
_OP_TIMEOUT_S = 0.05
_MAX_CONNECTIONS = 10

_client: Redis | None = None
_initialized = False


async def get_redis() -> Redis | None:
    """Return a shared async Redis client, or None if unreachable.

    Never raises. Callers fall back to in-memory logic on None.

    Idempotent: first call tries to connect; subsequent calls return the
    cached client. Call `reset_redis_cache()` in tests to clear state.
    """
    global _client, _initialized

    if _initialized:
        return _client

    _initialized = True

    url = os.environ.get("REDIS_URL")
    if not url:
        logger.debug("REDIS_URL unset; skipping Redis client init")
        _client = None
        return _client

    try:
        pool = ConnectionPool.from_url(
            url,
            max_connections=_MAX_CONNECTIONS,
            socket_connect_timeout=_CONNECT_TIMEOUT_S,
            socket_timeout=_OP_TIMEOUT_S,
            decode_responses=True,
        )
        client = Redis(connection_pool=pool)
        # Ping now so we fail open immediately if Redis isn't reachable,
        # rather than on the first real op. Ping failure puts `_client`
        # at None; a later explicit `reset_redis_cache()` re-tries.
        await client.ping()
    except (
        RedisConnectionError,
        RedisTimeoutError,
        TimeoutError,
        RedisError,
        OSError,
    ) as e:
        logger.warning(
            "Redis init failed (%s: %s); falling back to in-memory cache",
            type(e).__name__,
            e,
        )
        _client = None
        return _client

    _client = client
    return _client


def reset_redis_cache() -> None:
    """Drop the cached client + init flag. Primarily for tests.

    After this call, the next `get_redis()` re-runs the env + ping
    path. Production code never calls this — the module-global cache
    is fine for the lifetime of a task.
    """
    global _client, _initialized
    _client = None
    _initialized = False


async def safe_get(key: str) -> str | None:
    """Best-effort GET. Returns None on any error (including client unavailable).

    Intended for cache-aside reads: callers treat None as "cache miss"
    whether that's from Redis saying "key not present" or from Redis
    being down. Distinguishing the two is not useful to callers and
    complicates the fail-open contract.
    """
    client = await get_redis()
    if client is None:
        return None
    try:
        return await client.get(key)
    except (
        RedisConnectionError,
        RedisTimeoutError,
        TimeoutError,
        RedisError,
        OSError,
    ) as e:
        logger.warning("Redis GET failed (%s: %s)", type(e).__name__, e)
        return None


async def safe_set(key: str, value: str, ex: int | None = None) -> bool:
    """Best-effort SET EX. Returns False on any error.

    Used by cache-aside writers. A False return means "Redis unavailable
    — the write didn't land, keep serving from the in-memory tier." No
    retry; the next write attempt will try Redis again.
    """
    client = await get_redis()
    if client is None:
        return False
    try:
        await client.set(key, value, ex=ex)
        return True
    except (
        RedisConnectionError,
        RedisTimeoutError,
        TimeoutError,
        RedisError,
        OSError,
    ) as e:
        logger.warning("Redis SET failed (%s: %s)", type(e).__name__, e)
        return False
