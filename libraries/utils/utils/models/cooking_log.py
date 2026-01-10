"""CookingLog model."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from palateful_utils.db.base import Base

if TYPE_CHECKING:
    from palateful_utils.db.models.recipe import Recipe


class CookingLog(Base):
    """CookingLog model - records when a recipe was cooked."""

    __tablename__ = "cooking_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scale_factor: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    cooked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    pantry_id: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="cooking_logs")
