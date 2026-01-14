"""PantryIngredient model - ingredients in a pantry."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.ingredient import Ingredient
    from utils.models.pantry import Pantry


class PantryIngredient(JoinsBase):
    """PantryIngredient model - ingredients in a pantry."""

    __tablename__ = "pantry_ingredients"

    # created_at, updated_at, archived_at inherited from JoinsBase
    quantity_display: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_display: Mapped[str] = mapped_column(String, nullable=False)
    quantity_normalized: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_normalized: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Foreign keys (composite primary key)
    pantry_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("pantries.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("ingredients.id"), primary_key=True
    )

    # Relationships
    pantry: Mapped["Pantry"] = relationship(back_populates="pantry_ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="pantry_ingredients")

    __table_args__ = (
        UniqueConstraint("pantry_id", "ingredient_id", name="uq_pantry_ingredients"),
    )
