import uuid

from sqlalchemy import UUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.joins_base import JoinsBase


class Base(JoinsBase):
    """Base class for all main models (with ID and timestamps)."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    def __repr__(self) -> str:
        return self.get_repr(["id"])
