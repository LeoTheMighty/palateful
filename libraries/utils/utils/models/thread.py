"""Thread model for AI chat conversations."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from palateful_utils.db.base import Base

if TYPE_CHECKING:
    from palateful_utils.db.models.chat import Chat
    from palateful_utils.db.models.user import User


class Thread(Base):
    """Thread model - represents an AI chat conversation."""

    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Foreign keys
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="threads")
    chats: Mapped[list["Chat"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="Chat.created_at"
    )

    __table_args__ = (Index("ix_threads_user_id", "user_id"),)
