"""MealEvent model - A planned meal on the calendar."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.pantry import Pantry
    from utils.models.recipe import Recipe
    from utils.models.user import User
    from utils.models.meal_event_participant import MealEventParticipant
    from utils.models.prep_step import PrepStep
    from utils.models.shopping_list import ShoppingList


class MealEvent(Base):
    """A planned meal on the calendar."""

    __tablename__ = "meal_events"

    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    meal_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # breakfast | lunch | dinner | snack

    # Status: planned | shopping | prepping | cooking | completed | skipped
    status: Mapped[str] = mapped_column(String(20), default="planned")

    # Notification preferences
    notify_prep_start: Mapped[bool] = mapped_column(Boolean, default=True)
    prep_start_offset_minutes: Mapped[int] = mapped_column(
        Integer, default=60
    )  # Notify X mins before
    notify_cook_start: Mapped[bool] = mapped_column(Boolean, default=True)
    cook_start_offset_minutes: Mapped[int] = mapped_column(
        Integer, default=30
    )

    # Sharing settings
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)

    # Recurring event settings
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # e.g., "WEEKLY:SUN,TUE" or "DAILY" or "MONTHLY:1,15"
    recurrence_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    parent_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_events.id", ondelete="SET NULL"),
        nullable=True,
    )  # For instances of recurring events, points to the parent

    # Foreign keys
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    pantry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pantries.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    recipe: Mapped["Recipe | None"] = relationship()
    owner: Mapped["User"] = relationship()
    pantry: Mapped["Pantry | None"] = relationship()
    parent_event: Mapped["MealEvent | None"] = relationship(
        remote_side="MealEvent.id",
        foreign_keys=[parent_event_id],
    )
    participants: Mapped[list["MealEventParticipant"]] = relationship(
        back_populates="meal_event", cascade="all, delete-orphan"
    )
    prep_steps: Mapped[list["PrepStep"]] = relationship(
        back_populates="meal_event", cascade="all, delete-orphan"
    )
    shopping_list: Mapped["ShoppingList | None"] = relationship(
        back_populates="meal_event", uselist=False
    )
