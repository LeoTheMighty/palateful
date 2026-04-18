"""UserActivity model — user-facing activity feed items."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


class UserActivity(Base):
    """User-facing activity feed item (imports, partner actions, reminders)."""

    __tablename__ = "user_activities"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    action_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_user_activities_user_created", "user_id", "created_at"),
        # Hot-path partial index for the default feed query
        # (`archived_at IS NULL`) — added by the activity-hub redesign
        # epic. Scan is served by this index when the Activity tab
        # (Notifications or Imports) requests the default feed.
        Index(
            "ix_user_activities_user_created_active",
            "user_id",
            text("created_at DESC"),
            postgresql_where=text("archived_at IS NULL"),
        ),
        # See-all partial index for the Imports-tab See-all footer
        # (`archived_at IS NOT NULL`), ordered newest-archive-first.
        Index(
            "ix_user_activities_user_archived",
            "user_id",
            text("archived_at DESC"),
            postgresql_where=text("archived_at IS NOT NULL"),
        ),
    )
