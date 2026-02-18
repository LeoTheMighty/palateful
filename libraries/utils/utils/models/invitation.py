"""Invitation model - unified resource-sharing invitation with full lifecycle."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


class Invitation(Base):
    """Unified invitation for sharing any resource (recipe book, pantry, shopping list, meal event)."""

    __tablename__ = "invitations"

    # Who sent the invitation
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Who receives the invitation (null for email-only invites to non-users)
    to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Email for inviting non-users
    to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Resource being shared: "recipe_book" | "pantry" | "shopping_list" | "meal_event"
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Role offered: "editor" | "viewer" | "cohost" | "guest"
    role_offered: Mapped[str] = mapped_column(String(20), nullable=False)

    # Status: "pending" | "accepted" | "declined" | "revoked" | "expired"
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Optional message from the inviter
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # When the recipient responded
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # When the invitation expires
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    from_user: Mapped["User"] = relationship(
        foreign_keys=[from_user_id], back_populates="sent_invitations"
    )
    to_user: Mapped["User | None"] = relationship(
        foreign_keys=[to_user_id], back_populates="received_invitations"
    )

    __table_args__ = (
        Index("ix_invitations_resource", "resource_type", "resource_id"),
        Index("ix_invitations_to_user_id", "to_user_id"),
        Index("ix_invitations_from_user_id", "from_user_id"),
    )

    def __repr__(self) -> str:
        return self.get_repr(["id", "resource_type", "status"])
