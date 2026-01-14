from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class JoinsBase(DeclarativeBase):
    """Base class for join tables (no ID, just timestamps)."""

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def is_archived(self) -> bool:
        """Check if the record is archived."""
        return self.archived_at is not None

    def get_repr(self, attribute_names: list[str]) -> str:
        """Helper function to get a string representation of the record."""
        attributes = [f"{attr}={getattr(self, attr, None)}" for attr in attribute_names]
        return f"<{self.__class__.__name__} {', '.join(attributes)}>"

    def __repr__(self) -> str:
        return self.get_repr(["created_at"])
    