"""PrepStep model - A step in preparing a meal, potentially with wait times."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.meal_event import MealEvent
    from utils.models.recipe import Recipe


class PrepStep(Base):
    """A step in preparing a meal, potentially with wait times."""

    __tablename__ = "prep_steps"

    # Content
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)

    # Timing
    active_time_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Hands-on time
    wait_time_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Passive time (marinate, rise, etc.)
    wait_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # marinate | rise | chill | rest | freeze | thaw | brine | soak

    # Can this be done ahead of time?
    can_prep_ahead: Mapped[bool] = mapped_column(Boolean, default=False)
    max_prep_ahead_hours: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # How far in advance

    # Notification settings when attached to a meal event
    notify_when_done: Mapped[bool] = mapped_column(Boolean, default=True)

    # Status tracking (when in progress)
    # pending | in_progress | waiting | completed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wait_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Foreign keys
    meal_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_events.id", ondelete="CASCADE"),
        nullable=True,
    )
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    meal_event: Mapped["MealEvent | None"] = relationship(back_populates="prep_steps")
    recipe: Mapped["Recipe | None"] = relationship()
