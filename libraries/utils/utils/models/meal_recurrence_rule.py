"""MealRecurrenceRule model - a slot-based recurrence rule for meal planning."""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.recipe import Recipe
    from utils.models.user import User


class MealRecurrenceRule(Base):
    """A rule that materializes into concrete meal_events rows."""

    __tablename__ = "meal_recurrence_rules"

    __table_args__ = (
        Index(
            "ix_meal_recurrence_rules_materialized_through",
            "materialized_through",
        ),
        Index(
            "ix_meal_recurrence_rules_calendar_id",
            "calendar_id",
        ),
    )

    # Free-text title when recipe_id is null. Ignored when recipe_id is set —
    # the materialized row's title is pulled from recipe.name live.
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # breakfast | lunch | dinner | snack
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # List of weekday names, e.g. ["mon", "wed", "fri"].
    weekdays: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    # weekly | biweekly | monthly (monthly lands in editing epic)
    interval: Mapped[str] = mapped_column(String(20), nullable=False)

    # Non-null only when interval == "monthly": first | second | third | fourth | last
    monthly_nth: Mapped[str | None] = mapped_column(String(10), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # IANA tz name used to resolve per-slot local time to UTC on materialize.
    tz_name: Mapped[str] = mapped_column(String(64), nullable=False)

    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # High-water mark: materialize has populated events up to this date.
    materialized_through: Mapped[date | None] = mapped_column(Date, nullable=True)

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendars.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    recipe: Mapped["Recipe | None"] = relationship()
    owner: Mapped["User"] = relationship()
