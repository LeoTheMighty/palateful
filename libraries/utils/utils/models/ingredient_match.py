"""IngredientMatch model for caching ingredient matching decisions."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.ingredient import Ingredient
    from utils.models.user import User


class IngredientMatch(Base):
    """Caches ingredient matching decisions to reduce AI calls over time."""

    __tablename__ = "ingredient_matches"

    # Source text (normalized lowercase for lookup)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_text_normalized: Mapped[str] = mapped_column(Text, nullable=False)  # Lowercase for indexing

    # Match result
    matched_ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    match_type: Mapped[str] = mapped_column(String(20))  # exact | fuzzy | ai | user_selected
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    # User confirmation
    user_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    matched_ingredient: Mapped["Ingredient | None"] = relationship()
    user: Mapped["User | None"] = relationship()

    # Indexes for lookup
    __table_args__ = (
        Index("ix_ingredient_matches_source_text_normalized", "source_text_normalized"),
        Index("ix_ingredient_matches_user_confirmed", "user_confirmed"),
    )
