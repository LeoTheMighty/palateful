"""MealRecipe — ordered join between a Meal and a component Recipe."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.meal import Meal
    from utils.models.recipe import Recipe


class MealRecipe(JoinsBase):
    """One component row on a Meal.

    `recipe_id` is `ondelete RESTRICT` on purpose: user-facing deletes are
    soft archives, so the DB-level hard-delete path is only reachable via
    admin scripts or test cleanup. RESTRICT turns a silent orphaning bug
    into a loud IntegrityError.
    """

    __tablename__ = "meal_recipes"

    __table_args__ = (
        Index("ix_meal_recipes_recipe_id", "recipe_id"),
    )

    # created_at, updated_at, archived_at inherited from JoinsBase
    meal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meals.id", ondelete="CASCADE"),
        primary_key=True,
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Relationships
    meal: Mapped["Meal"] = relationship(back_populates="components")
    recipe: Mapped["Recipe"] = relationship(foreign_keys=[recipe_id])
