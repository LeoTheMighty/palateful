"""IngredientSubstitution model - substitution relationships."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.ingredient import Ingredient


class IngredientSubstitution(JoinsBase):
    """IngredientSubstitution model - substitution relationships."""

    __tablename__ = "ingredient_substitutions"

    # created_at, updated_at, archived_at inherited from JoinsBase
    context: Mapped[str | None] = mapped_column(String, nullable=True)  # baking, cooking, raw, any
    quality: Mapped[str] = mapped_column(String, nullable=False)  # perfect, good, workable
    ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Foreign keys (composite primary key)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True
    )
    substitute_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    ingredient: Mapped["Ingredient"] = relationship(
        foreign_keys=[ingredient_id], back_populates="substitutes_for"
    )
    substitute: Mapped["Ingredient"] = relationship(
        foreign_keys=[substitute_id], back_populates="substituted_by"
    )

    __table_args__ = (
        UniqueConstraint(
            "ingredient_id", "substitute_id", "context", name="uq_ingredient_substitutions"
        ),
    )
