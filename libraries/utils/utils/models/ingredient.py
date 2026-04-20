"""Ingredient model — post str-ing-4.

Per epic-ingredients-string-simplification (2026-04-20) the ingredients
table is a bag of display names, not an identity graph. Every write path
creates a fresh row per parsed ingredient name; no uniqueness, no
canonicalization, no cross-recipe matching. FKs from `recipe_ingredients`
/ `pantry_ingredients` / `pantry_ingredient_events` / `shopping_list_items`
remain so display-name lookups stay relational, but nothing cross-
references these rows for identity.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.pantry_ingredient import PantryIngredient
    from utils.models.recipe_ingredient import RecipeIngredient
    from utils.models.user import User


class Ingredient(Base):
    """Display-row for an ingredient name — no identity semantics."""

    __tablename__ = "ingredients"

    # id, created_at, updated_at, archived_at inherited from Base
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    flavor_profile: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), default=list, nullable=True
    )
    default_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Foreign keys
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    submitted_by: Mapped["User | None"] = relationship(back_populates="submitted_ingredients")
    pantry_ingredients: Mapped[list["PantryIngredient"]] = relationship(
        back_populates="ingredient"
    )
    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="ingredient"
    )
