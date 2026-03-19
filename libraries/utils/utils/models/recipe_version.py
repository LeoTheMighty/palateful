"""RecipeVersion model - immutable snapshot of recipe state at a point in time."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.joins_base import JoinsBase

if TYPE_CHECKING:
    from utils.models.recipe import Recipe


class RecipeVersion(JoinsBase):
    """Immutable snapshot of a recipe's state before an edit.

    Versions are append-only — they cannot be modified or deleted.
    Although JoinsBase provides updated_at/archived_at, this model
    does not use them. The migration omits those columns entirely.
    """

    __tablename__ = "recipe_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)

    # Foreign keys
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("recipe_id", "version_number", name="uq_recipe_versions_recipe_version"),
        Index("ix_recipe_versions_recipe_id", "recipe_id"),
    )
