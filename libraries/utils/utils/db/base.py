"""Re-export Base class for migrations."""

from utils.models.joins_base import JoinsBase

# Re-export JoinsBase as Base for Alembic migrations
# JoinsBase is the actual DeclarativeBase that holds the metadata
Base = JoinsBase

__all__ = ["Base"]
