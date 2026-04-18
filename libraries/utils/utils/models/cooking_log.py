"""CookingLog model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import UUID, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.meal import Meal
    from utils.models.recipe import Recipe


class CookingLog(Base):
    """CookingLog model - records when a recipe (or Meal) was cooked.

    Target semantics (post mcal-1):
      - Recipe-only log: `recipe_id` set, `meal_id` NULL, `parent_meal_log_id` NULL.
      - Meal-level parent log: `recipe_id` NULL, `meal_id` set, `parent_meal_log_id` NULL.
      - Fan-out child log: `recipe_id` set, `meal_id` NULL, `parent_meal_log_id` set
        (points to the parent Meal-level log). Child rows preserve recipe-level
        cook history for "last cooked" queries when a Meal event is marked cooked.

    The `ck_cooking_logs_target` CHECK constraint enforces this.
    """

    __tablename__ = "cooking_logs"

    __table_args__ = (
        CheckConstraint(
            "(num_nonnulls(recipe_id, meal_id) = 1) OR "
            "(parent_meal_log_id IS NOT NULL AND recipe_id IS NOT NULL AND meal_id IS NULL)",
            name="ck_cooking_logs_target",
        ),
    )

    # id, created_at, updated_at, archived_at inherited from Base
    scale_factor: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    cooked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys. recipe_id is nullable to support Meal-level parent rows;
    # the CHECK constraint ensures any given row has exactly one target
    # (recipe or meal) *or* is a fan-out child (recipe_id + parent_meal_log_id).
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("recipes.id"), nullable=True
    )
    meal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("meals.id", ondelete="SET NULL"), nullable=True
    )
    parent_meal_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("cooking_logs.id", ondelete="CASCADE"), nullable=True
    )
    pantry_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("pantries.id"))

    # Relationships
    recipe: Mapped["Recipe | None"] = relationship(back_populates="cooking_logs")
    meal: Mapped["Meal | None"] = relationship()
    parent_meal_log: Mapped["CookingLog | None"] = relationship(
        remote_side="CookingLog.id",
        foreign_keys=[parent_meal_log_id],
    )
