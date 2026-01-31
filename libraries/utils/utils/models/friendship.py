"""Friendship model - bidirectional friendship between users."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.user import User


class Friendship(JoinsBase):
    """Bidirectional friendship between users.

    When users become friends, TWO records are created:
    - (user_a, user_b)
    - (user_b, user_a)

    This allows efficient querying: WHERE user_id = ? gets all friends.
    """

    __tablename__ = "friendships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    friend_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="friendships",
    )
    friend: Mapped["User"] = relationship(
        "User",
        foreign_keys=[friend_id],
    )

    def __repr__(self) -> str:
        return self.get_repr(["user_id", "friend_id"])
