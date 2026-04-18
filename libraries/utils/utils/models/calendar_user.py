"""CalendarUser model - join table for calendar membership."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.calendar import Calendar
    from utils.models.user import User


class CalendarUser(JoinsBase):
    """Calendar membership with role."""

    __tablename__ = "calendar_users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor')",
            name="ck_calendar_users_role",
        ),
        Index("ix_calendar_users_user_archived", "user_id", "archived_at"),
        Index("ix_calendar_users_calendar_id", "calendar_id"),
        # DB-enforced: exactly one active owner per calendar. The
        # ownership-transfer handler in update_calendar_member.py relies
        # on this constraint as the last-line guard against the racy case
        # where two concurrent transfers slip past the row-level
        # SELECT ... FOR UPDATE serialization.
        Index(
            "uq_calendar_users_one_owner_active",
            "calendar_id",
            unique=True,
            postgresql_where=text("role = 'owner' AND archived_at IS NULL"),
        ),
    )

    # created_at, updated_at, archived_at inherited from JoinsBase.
    #
    # NOTE (cal-share-1 handoff): the composite PK (calendar_id, user_id)
    # means re-adding a previously-archived member via plain INSERT will
    # PK-collide. The sharing epic must either switch to a surrogate-id
    # PK + unique index on `(calendar_id, user_id) WHERE archived_at IS
    # NULL` (matches recipe_book_user convention) or upsert via
    # UPDATE ... SET archived_at = NULL on re-add. Not relevant here
    # because this story only ever creates rows (on owner setup) or
    # archives them (on calendar delete) — never re-adds.
    role: Mapped[str] = mapped_column(
        String(16), default="editor", server_default="editor", nullable=False
    )

    # Composite primary key
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendars.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Who invited this user (null for original owners)
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Recency tracking — when user last viewed this calendar
    last_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    calendar: Mapped["Calendar"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
