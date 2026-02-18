"""InviteLink model - shareable link tokens for resource sharing."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


class InviteLink(Base):
    """Shareable link token for 'copy link to share' flows on any resource."""

    __tablename__ = "invite_links"

    # URL-safe random token
    token: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Who created the link
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Resource being shared: "recipe_book" | "pantry" | "shopping_list" | "meal_event"
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Role offered: "editor" | "viewer"
    role_offered: Mapped[str] = mapped_column(String(20), nullable=False)

    # Usage limits (null = unlimited)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Expiration
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Can be deactivated without deleting
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    created_by: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return self.get_repr(["id", "token", "resource_type"])
