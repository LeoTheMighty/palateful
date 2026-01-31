"""Friend request model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


class FriendRequest(Base):
    """Pending friend request between users."""

    __tablename__ = "friend_requests"

    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, accepted, declined

    # Relationships
    from_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[from_user_id],
        back_populates="sent_friend_requests",
    )
    to_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[to_user_id],
        back_populates="received_friend_requests",
    )

    def __repr__(self) -> str:
        return self.get_repr(["id", "from_user_id", "to_user_id", "status"])
