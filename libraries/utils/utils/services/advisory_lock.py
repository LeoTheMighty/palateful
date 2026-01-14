import hashlib
import logging

from sqlalchemy import Engine, text

from utils.constants import LOGGING_LEVEL

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)


class AdvisoryLock:
    """A class for acquiring and releasing advisory locks on the database."""

    def __init__(self, engine: Engine, key: str):
        """Initialize the AdvisoryLock class."""
        self.engine = engine
        self.key = self.hash_key(key)
        self.conn = None

    @staticmethod
    def hash_key(key: str) -> int:
        """Hash the key using a 64-bit integer."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) & ((1 << 63) - 1)

    def __enter__(self):
        """Acquire the advisory lock."""
        self.conn = self.engine.connect()
        self.conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": self.key})
        return True

    def __exit__(self, exc_type, exc_val, tb):
        """Release the advisory lock."""
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": self.key})
            self.conn.close()
