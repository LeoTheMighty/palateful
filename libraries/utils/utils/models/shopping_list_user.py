"""ShoppingListUser model - join table for shopping list membership/sharing."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.shopping_list import ShoppingList
    from utils.models.user import User


class ShoppingListUser(JoinsBase):
    """Join table for shopping list membership/sharing."""

    __tablename__ = "shopping_list_users"

    # created_at, updated_at, archived_at inherited from JoinsBase

    # Composite primary key
    shopping_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Role: owner | editor | viewer
    role: Mapped[str] = mapped_column(String(20), default="editor")

    # Notification preferences per user per list
    notify_on_add: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_check: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_on_deadline: Mapped[bool] = mapped_column(Boolean, default=True)

    # Last seen cursor for unread tracking
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    shopping_list: Mapped["ShoppingList"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="shopping_list_memberships")

    __table_args__ = (
        UniqueConstraint(
            "shopping_list_id", "user_id", name="uq_shopping_list_users"
        ),
    )
