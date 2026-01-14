"""CookingLog model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.recipe import Recipe


class CookingLog(Base):
    """CookingLog model - records when a recipe was cooked."""

    __tablename__ = "cooking_logs"

    # id, created_at, updated_at, archived_at inherited from Base
    scale_factor: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    cooked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys
    recipe_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("recipes.id"))
    pantry_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("pantries.id"))

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="cooking_logs")
