"""PantryUser model - join table for pantry membership."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.pantry import Pantry
    from utils.models.user import User


class PantryUser(JoinsBase):
    """PantryUser model - join table for pantry membership."""

    __tablename__ = "pantry_users"

    # created_at, updated_at, archived_at inherited from JoinsBase
    role: Mapped[str] = mapped_column(String, default="member")  # owner, member

    # Foreign keys (composite primary key)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    pantry_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("pantries.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="pantry_memberships")
    pantry: Mapped["Pantry"] = relationship(back_populates="members")

    __table_args__ = (UniqueConstraint("user_id", "pantry_id", name="uq_pantry_users"),)
