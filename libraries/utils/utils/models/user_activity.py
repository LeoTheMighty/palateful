"""UserActivity model — user-facing activity feed items."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.user import User


# Single source of truth for `user_activity.type` values that surface in
# the Notifications tab and contribute to the bell count. Adding a
# value here is the only way to make a type user-visible. Read by both
# `unread_count.py` (bell) and `list_activities.py` (Notifications
# tab) so the two numbers can never disagree.
#
# Current membership is intentionally narrow — `partner_action` is the
# only type push dispatch writes to `user_activities` for user-facing
# display today. `import_*` types are NOT listed: push for imports
# reads `import_items` directly (see abi-2a), and per-tab counts come
# from the `imports_actionable` field of the unread-count payload.
NOTIFICATION_TAB_TYPES: frozenset[str] = frozenset({"partner_action"})


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
