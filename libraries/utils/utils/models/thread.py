"""Thread model for AI chat conversations."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.chat import Chat
    from utils.models.user import User


class Thread(Base):
    """Thread model - represents an AI chat conversation."""

    __tablename__ = "threads"

    # id, created_at, updated_at, archived_at inherited from Base
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="threads")
    chats: Mapped[list["Chat"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="Chat.created_at"
    )

    __table_args__ = (Index("ix_threads_user_id", "user_id"),)
