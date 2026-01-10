"""Ingredient models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from palateful_utils.db.base import Base

if TYPE_CHECKING:
    from palateful_utils.db.models.pantry import PantryIngredient
    from palateful_utils.db.models.recipe import RecipeIngredient
    from palateful_utils.db.models.user import User


class Ingredient(Base):
    """Ingredient model with embedding support."""

    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    flavor_profile: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    default_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    pending_review: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Vector embedding (384 dimensions for all-MiniLM-L6-v2)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    # Foreign keys
    submitted_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingredients.id"), nullable=True
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


class IngredientSubstitution(Base):
    """IngredientSubstitution model - substitution relationships."""

    __tablename__ = "ingredient_substitutions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    context: Mapped[str | None] = mapped_column(String, nullable=True)  # baking, cooking, raw, any
    quality: Mapped[str] = mapped_column(String, nullable=False)  # perfect, good, workable
    ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Foreign keys
    ingredient_id: Mapped[str] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    substitute_id: Mapped[str] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE")
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
