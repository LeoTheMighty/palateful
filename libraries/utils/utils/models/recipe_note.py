"""RecipeNote model - append-only annotations on a recipe."""

import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.joins_base import JoinsBase


class RecipeNote(JoinsBase):
    """Append-only note attached to a recipe.

    Notes are not versioned — they are annotations that accumulate over time.
    They are captured in recipe version snapshots for historical viewing,
    but are never restored when a recipe version is restored.
    """

    __tablename__ = "recipe_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (Index("ix_recipe_notes_recipe_id", "recipe_id"),)
