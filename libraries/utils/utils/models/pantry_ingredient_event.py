"""PantryIngredientEvent model - audit trail for automatic pantry mutations.

Rows are inserted by the event hooks (pantry-3 / pantry-4) whenever they
change a pantry_ingredient so we can answer "why does my pantry say X?"
without depending on structured log retention.
"""

import uuid
from decimal import Decimal

from sqlalchemy import UUID, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.base import Base


class PantryIngredientEvent(Base):
    """Audit entry for an automatic mutation on a pantry_ingredient."""

    __tablename__ = "pantry_ingredient_events"

    # id, created_at, updated_at, archived_at inherited from Base
    pantry_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("pantries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    delta_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    source_meal_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("meal_events.id", ondelete="SET NULL"), nullable=True
    )
