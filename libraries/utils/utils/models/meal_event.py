"""MealEvent model - A planned meal on the calendar."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.meal import Meal
    from utils.models.meal_event_participant import MealEventParticipant
    from utils.models.pantry import Pantry
    from utils.models.prep_step import PrepStep
    from utils.models.recipe import Recipe
    from utils.models.shopping_list import ShoppingList
    from utils.models.user import User


class MealEvent(Base):
    """A planned meal on the calendar."""

    __tablename__ = "meal_events"

    __table_args__ = (
        Index(
            "uq_meal_events_rule_scheduled_at",
            "recurrence_rule_id",
            "scheduled_at",
            unique=True,
            postgresql_where=text("recurrence_rule_id IS NOT NULL"),
        ),
        Index(
            "ix_meal_events_calendar_id_scheduled_at",
            "calendar_id",
            "scheduled_at",
        ),
        Index("ix_meal_events_meal_id", "meal_id"),
        # At most one of recipe_id / meal_id may be set. Both-null is legal
        # (free-text event). Both-set is rejected.
        CheckConstraint(
            "num_nonnulls(recipe_id, meal_id) <= 1",
            name="ck_meal_events_recipe_xor_meal",
        ),
    )

    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    meal_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # breakfast | lunch | dinner | snack

    # Status: planned | shopping | prepping | cooking | completed | skipped
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)

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
    recurrence_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_recurrence_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Foreign keys
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )
    meal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meals.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pantry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pantries.id", ondelete="SET NULL"),
        nullable=True,
    )

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendars.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    recipe: Mapped["Recipe | None"] = relationship()
    meal: Mapped["Meal | None"] = relationship()
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
