"""Meal model — a named grouping of 2+ recipes within a recipe_book."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.meal_recipe import MealRecipe
    from utils.models.recipe_book import RecipeBook


class Meal(Base):
    """A reusable named grouping of component recipes.

    `share_token` column exists (no second migration needed when sharing
    ships) but no endpoint in epic-meals-create-and-view reads or writes
    it. The public read path lives in the sharing-and-ai epic.
    """

    __tablename__ = "meals"

    __table_args__ = (
        Index("ix_meals_recipe_book_id", "recipe_book_id"),
        Index(
            "ix_meals_share_token",
            "share_token",
            unique=True,
            postgresql_where=text("share_token IS NOT NULL"),
        ),
    )

    # id, created_at, updated_at, archived_at inherited from Base
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    recipe_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipe_books.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Matches Recipe.share_token length — `secrets.token_urlsafe(15)` yields
    # a 20-char URL-safe string. The sharing-and-ai epic writes these.
    share_token: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    recipe_book: Mapped["RecipeBook"] = relationship(foreign_keys=[recipe_book_id])
    components: Mapped[list["MealRecipe"]] = relationship(
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealRecipe.order_index",
    )
