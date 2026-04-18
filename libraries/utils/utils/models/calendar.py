"""Calendar model - first-class shareable container for meal_events and recurrence rules."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.calendar_user import CalendarUser
    from utils.models.user import User


class Calendar(Base):
    """A shareable container for planned meals and recurrence rules."""

    __tablename__ = "calendars"

    __table_args__ = (
        # DB-enforced invariant: exactly one default calendar per user that
        # is not archived.
        Index(
            "uq_calendars_owner_is_default_active",
            "owner_id",
            unique=True,
            postgresql_where=text("is_default = true AND archived_at IS NULL"),
        ),
    )

    # id, created_at, updated_at, archived_at inherited from Base
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Reserved hex color (not surfaced in UI yet).
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    members: Mapped[list["CalendarUser"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )
