"""PantryUser model - join table for pantry membership."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.pantry import Pantry
    from utils.models.user import User


class PantryUser(JoinsBase):
    """PantryUser model - join table for pantry membership."""

    __tablename__ = "pantry_users"

    # created_at, updated_at, archived_at inherited from JoinsBase
    role: Mapped[str] = mapped_column(String, default="editor")  # owner, editor, viewer

    # Foreign keys (composite primary key)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    pantry_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("pantries.id", ondelete="CASCADE"), primary_key=True
    )

    # Who invited this user (null for owners / original members)
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="pantry_memberships")
    pantry: Mapped["Pantry"] = relationship(back_populates="members")

    __table_args__ = (UniqueConstraint("user_id", "pantry_id", name="uq_pantry_users"),)
