"""ActiveTimer model - An active timer for cooking."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.meal_event import MealEvent
    from utils.models.recipe_step import RecipeStep
    from utils.models.user import User


class ActiveTimer(Base):
    """An active timer for cooking."""

    __tablename__ = "active_timers"

    # Timer info
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    # State: running | paused | completed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    elapsed_when_paused: Mapped[int] = mapped_column(
        Integer, default=0
    )  # seconds

    # Notification
    notify_on_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    meal_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_events.id", ondelete="CASCADE"),
        nullable=True,
    )
    recipe_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipe_steps.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship()
    meal_event: Mapped["MealEvent | None"] = relationship()
    recipe_step: Mapped["RecipeStep | None"] = relationship()

    @property
    def remaining_seconds(self) -> int:
        """Calculate remaining seconds on the timer."""
        if self.status == "paused":
            return self.duration_seconds - self.elapsed_when_paused
        elif self.status == "running":
            elapsed = (datetime.now(tz=timezone.utc) - self.started_at).total_seconds()
            return max(0, self.duration_seconds - int(elapsed) - self.elapsed_when_paused)
        return 0

    @property
    def is_expired(self) -> bool:
        """Check if the timer has expired."""
        return self.status == "running" and self.remaining_seconds <= 0
