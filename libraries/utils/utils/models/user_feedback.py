"""UserFeedback model for the feedback inbox."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


FEEDBACK_CATEGORIES = ("bug", "idea", "praise", "other")
FEEDBACK_STATUSES = ("unread", "read", "archived")
FEEDBACK_MAX_BODY_LENGTH = 4000


class UserFeedback(Base):
    """User-submitted feedback entry in the admin inbox.

    Body is bounded (1..4000) and enforced at both Pydantic and DB layers.
    Status transitions are one-way informational — archive is terminal.
    `context` is a free-form JSONB blob holding the tight Pydantic-validated
    envelope (app_version, platform, route, recipe_id) captured at submit
    time.
    """

    __tablename__ = "user_feedbacks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        default="unread",
        server_default="unread",
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        CheckConstraint(
            "length(body) BETWEEN 1 AND 4000",
            name="ck_user_feedbacks_body_length",
        ),
        CheckConstraint(
            "category IS NULL OR category IN ('bug', 'idea', 'praise', 'other')",
            name="ck_user_feedbacks_category",
        ),
        CheckConstraint(
            "status IN ('unread', 'read', 'archived')",
            name="ck_user_feedbacks_status",
        ),
        Index(
            "ix_user_feedbacks_status_created",
            "status",
            text("created_at DESC"),
        ),
        Index(
            "ix_user_feedbacks_user",
            "user_id",
        ),
    )

    def __repr__(self) -> str:
        return self.get_repr(["id", "user_id", "status", "category"])
