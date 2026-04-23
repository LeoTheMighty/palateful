"""Async counterpart of AdvisoryLock (aam-2).

Acquires/releases Postgres transaction-level advisory locks from an
AsyncSession. Mirrors the sync `AdvisoryLock` contract (same key hash,
same lock namespace) so a sync caller and an async caller contending
for the same key serialize correctly against each other.
"""

import hashlib
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from utils.constants import LOGGING_LEVEL

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)


class AsyncAdvisoryLock:
    """Async advisory lock anchored on a dedicated asyncpg connection.

    Matches `AdvisoryLock.hash_key` exactly — sync and async callers on
    the same key contend against the same Postgres lock (advisory locks
    are process-agnostic; the backend sees one key regardless of driver).
    """

    def __init__(self, engine: AsyncEngine, key: str):
        self.engine = engine
        self.key = self.hash_key(key)
        self.conn = None

    @staticmethod
    def hash_key(key: str) -> int:
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) & ((1 << 63) - 1)

    async def __aenter__(self):
        self.conn = await self.engine.connect()
        await self.conn.execute(
            text("SELECT pg_advisory_lock(:k)"), {"k": self.key}
        )
        return True

    async def __aexit__(self, exc_type, exc_val, tb):
        try:
            if exc_type:
                await self.conn.rollback()
            else:
                await self.conn.commit()
        finally:
            await self.conn.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": self.key}
            )
            await self.conn.close()
