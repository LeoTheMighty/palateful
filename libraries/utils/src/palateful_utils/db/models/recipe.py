"""Recipe models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from palateful_utils.db.base import Base

if TYPE_CHECKING:
    from palateful_utils.db.models.cooking_log import CookingLog
    from palateful_utils.db.models.ingredient import Ingredient
    from palateful_utils.db.models.user import User


class RecipeBook(Base):
    """RecipeBook model - collection of recipes."""

    __tablename__ = "recipe_books"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    members: Mapped[list["RecipeBookUser"]] = relationship(
        back_populates="recipe_book", cascade="all, delete-orphan"
    )
    recipes: Mapped[list["Recipe"]] = relationship(
        back_populates="recipe_book", cascade="all, delete-orphan"
    )


class RecipeBookUser(Base):
    """RecipeBookUser model - join table for recipe book membership."""

    __tablename__ = "recipe_book_users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, default="member")  # owner, editor, viewer
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Foreign keys
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipe_book_id: Mapped[str] = mapped_column(
        ForeignKey("recipe_books.id", ondelete="CASCADE")
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="recipe_book_memberships")
    recipe_book: Mapped["RecipeBook"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "recipe_book_id", name="uq_recipe_book_users"),
    )


class Recipe(Base):
    """Recipe model."""

    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    servings: Mapped[int] = mapped_column(Integer, default=1)
    prep_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes
    cook_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Foreign keys
    recipe_book_id: Mapped[str] = mapped_column(
        ForeignKey("recipe_books.id", ondelete="CASCADE")
    )

    # Relationships
    recipe_book: Mapped["RecipeBook"] = relationship(back_populates="recipes")
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    cooking_logs: Mapped[list["CookingLog"]] = relationship(back_populates="recipe")


class RecipeIngredient(Base):
    """RecipeIngredient model - ingredients in a recipe."""

    __tablename__ = "recipe_ingredients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    quantity_display: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_display: Mapped[str] = mapped_column(String, nullable=False)
    quantity_normalized: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_normalized: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Foreign keys
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.id"))

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_ingredients")

    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredients"),
    )
