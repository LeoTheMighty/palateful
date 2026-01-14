"""Ingredient model."""

import uuid
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, String, UUID
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.ingredient_substitution import IngredientSubstitution
    from utils.models.pantry_ingredient import PantryIngredient
    from utils.models.recipe_ingredient import RecipeIngredient
    from utils.models.user import User


class Ingredient(Base):
    """Ingredient model with embedding support."""

    __tablename__ = "ingredients"

    # id, created_at, updated_at, archived_at inherited from Base
    canonical_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    flavor_profile: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    default_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    pending_review: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Vector embedding (384 dimensions for all-MiniLM-L6-v2)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    # Foreign keys
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID, ForeignKey("ingredients.id"), nullable=True
    )

    # Relationships
    submitted_by: Mapped["User | None"] = relationship(back_populates="submitted_ingredients")
    pantry_ingredients: Mapped[list["PantryIngredient"]] = relationship(
        back_populates="ingredient"
    )
    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="ingredient"
    )
    substitutes_for: Mapped[list["IngredientSubstitution"]] = relationship(
        foreign_keys="IngredientSubstitution.ingredient_id",
        back_populates="ingredient",
        cascade="all, delete-orphan",
    )
    substituted_by: Mapped[list["IngredientSubstitution"]] = relationship(
        foreign_keys="IngredientSubstitution.substitute_id",
        back_populates="substitute",
        cascade="all, delete-orphan",
    )
    parent: Mapped["Ingredient | None"] = relationship(
        "Ingredient", remote_side="Ingredient.id", back_populates="children"
    )
    children: Mapped[list["Ingredient"]] = relationship(
        "Ingredient", back_populates="parent"
    )
