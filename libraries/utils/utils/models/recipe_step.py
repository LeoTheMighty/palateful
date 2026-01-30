"""RecipeStep model - A single instruction step in a recipe with timing metadata."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.recipe import Recipe


class RecipeStep(Base):
    """A single instruction step in a recipe with timing metadata."""

    __tablename__ = "recipe_steps"

    # Content
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)

    # Timing (optional - can be null for simple steps)
    active_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timer triggers (detected times in the instruction)
    # e.g., [{"duration_minutes": 25, "label": "bake"}, {"duration_minutes": 5, "label": "rest"}]
    timers: Mapped[list[dict] | None] = mapped_column(JSONB, default=list, nullable=True)

    # Wait/passive time
    wait_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wait_type: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # marinate | rise | chill | rest | freeze | thaw | brine | soak
    wait_min_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Minimum wait
    wait_max_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Maximum wait

    # Flags
    can_prep_ahead: Mapped[bool] = mapped_column(Boolean, default=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)

    # Foreign key
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="steps")
