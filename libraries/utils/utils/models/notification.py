"""Notification model for delivery tracking."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.suggestion import Suggestion
    from utils.models.user import User


class Notification(Base):
    """
    Notification model for tracking delivery across channels.

    Each suggestion can generate multiple notifications (push, email, in-app),
    and this model tracks the delivery status of each.
    """

    __tablename__ = "notifications"

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "suggestion" | "reminder" | "system"

    # Delivery
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "push" | "email" | "in_app"
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # "pending" | "sent" | "failed" | "read"

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("suggestions.id", ondelete="CASCADE"), nullable=True
    )

    # Push-specific fields
    push_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fcm_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Email-specific fields
    email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ses_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Delivery timestamp
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="notifications")
    suggestion: Mapped["Suggestion | None"] = relationship(back_populates="notifications")

    def __repr__(self) -> str:
        return self.get_repr(["id", "channel", "status", "notification_type"])
