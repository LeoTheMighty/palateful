"""ShoppingList and ShoppingListItem models."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.ingredient import Ingredient
    from utils.models.meal_event import MealEvent
    from utils.models.pantry import Pantry
    from utils.models.recipe import Recipe
    from utils.models.user import User


class ShoppingList(Base):
    """A shopping list for a meal event or standalone use."""

    __tablename__ = "shopping_lists"

    # Name for standalone lists or auto-generated from meal event
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status: pending | in_progress | completed
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Foreign keys
    meal_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_events.id", ondelete="CASCADE"),
        nullable=True,
    )
    pantry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pantries.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    meal_event: Mapped["MealEvent | None"] = relationship(back_populates="shopping_list")
    pantry: Mapped["Pantry | None"] = relationship()
    owner: Mapped["User"] = relationship()
    items: Mapped[list["ShoppingListItem"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan"
    )


class ShoppingListItem(Base):
    """An item on a shopping list."""

    __tablename__ = "shopping_list_items"

    # Item info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Status
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Source (which recipe needed this)
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Smart shopping - from pantry
    # "You have 1 cup, need 2 cups, buy 1 cup"
    already_have_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    # Category for grouping in store (produce, dairy, etc.)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Foreign keys
    shopping_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    shopping_list: Mapped["ShoppingList"] = relationship(back_populates="items")
    ingredient: Mapped["Ingredient | None"] = relationship()
    recipe: Mapped["Recipe | None"] = relationship()
    checked_by: Mapped["User | None"] = relationship()
