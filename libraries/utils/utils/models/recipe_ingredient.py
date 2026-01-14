"""RecipeIngredient model - ingredients in a recipe."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.ingredient import Ingredient
    from utils.models.recipe import Recipe


class RecipeIngredient(JoinsBase):
    """RecipeIngredient model - ingredients in a recipe."""

    __tablename__ = "recipe_ingredients"

    # created_at, updated_at, archived_at inherited from JoinsBase
    quantity_display: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_display: Mapped[str] = mapped_column(String, nullable=False)
    quantity_normalized: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_normalized: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Foreign keys (composite primary key)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("ingredients.id"), primary_key=True
    )

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_ingredients")

    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredients"),
    )
