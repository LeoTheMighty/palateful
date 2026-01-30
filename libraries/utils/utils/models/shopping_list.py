"""ShoppingList and ShoppingListItem models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.ingredient import Ingredient
    from utils.models.meal_event import MealEvent
    from utils.models.pantry import Pantry
    from utils.models.recipe import Recipe
    from utils.models.shopping_list_user import ShoppingListUser
    from utils.models.user import User


class ShoppingList(Base):
    """A shopping list that can be shared between users."""

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

    # === Sharing & Real-time ===

    # Whether this list is shared (enables real-time features)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)

    # Short code for easy sharing (e.g., "ABC123")
    share_code: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)

    # Default deadline for items without explicit due dates
    default_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Whether to auto-populate from upcoming meal events
    auto_populate_from_calendar: Mapped[bool] = mapped_column(Boolean, default=True)

    # Calendar range for auto-population (days ahead)
    calendar_lookahead_days: Mapped[int] = mapped_column(Integer, default=7)

    # === Widget Display Settings ===

    # Color theme for the floating widget
    widget_color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color

    # Sort order preference: deadline | category | name | checked | added_at
    sort_by: Mapped[str] = mapped_column(String(20), default="deadline")

    # Relationships
    meal_event: Mapped["MealEvent | None"] = relationship(back_populates="shopping_list")
    pantry: Mapped["Pantry | None"] = relationship()
    owner: Mapped["User"] = relationship()
    items: Mapped[list["ShoppingListItem"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan"
    )
    members: Mapped[list["ShoppingListUser"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan"
    )


class ShoppingListItem(Base):
    """An item on a shopping list with deadline tracking."""

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

    # === Deadline & Meal Event Integration ===

    # When this specific ingredient is needed by
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Which meal event this item is for (can differ from list's meal_event_id for aggregated lists)
    meal_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Why this ingredient is needed at this time
    # Examples: "marinating", "prep_start", "cook_start", "serving"
    due_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Priority level (1-5, where 1 is most urgent)
    priority: Mapped[int] = mapped_column(Integer, default=3)

    # === Collaboration Features ===

    # Who added this item
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Optional note (e.g., "get organic", "brand X preferred")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # When the item was checked (for sorting/history)
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Assignee (who should get this item)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # === Store Location Hints ===

    # Aisle or section in store
    store_section: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Store-specific ordering index
    store_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    shopping_list: Mapped["ShoppingList"] = relationship(back_populates="items")
    ingredient: Mapped["Ingredient | None"] = relationship()
    recipe: Mapped["Recipe | None"] = relationship()
    checked_by: Mapped["User | None"] = relationship(
        foreign_keys=[checked_by_user_id]
    )
    meal_event: Mapped["MealEvent | None"] = relationship()
    added_by: Mapped["User | None"] = relationship(
        foreign_keys=[added_by_user_id]
    )
    assigned_to: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_to_user_id]
    )
