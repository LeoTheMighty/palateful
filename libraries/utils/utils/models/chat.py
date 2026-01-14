"""Chat model for AI messages."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.thread import Thread


class Chat(Base):
    """Chat model - represents a single message in a thread."""

    __tablename__ = "chats"

    # id, created_at, updated_at, archived_at inherited from Base
    role: Mapped[str] = mapped_column(String, nullable=False)  # user, assistant, system, tool
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OpenAI-specific fields
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Usage tracking
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)

    # Foreign keys
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("threads.id", ondelete="CASCADE")
    )

    # Relationships
    thread: Mapped["Thread"] = relationship(back_populates="chats")

    __table_args__ = (Index("ix_chats_thread_id", "thread_id"),)
