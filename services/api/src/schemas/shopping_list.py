"""Shopping list related Pydantic schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ShoppingListItemCreate(BaseModel):
    """Request schema for adding an item to a shopping list."""

    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    category: str | None = None
    ingredient_id: str | None = None
    recipe_id: str | None = None


class ShoppingListItemUpdate(BaseModel):
    """Request schema for updating a shopping list item."""

    name: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    is_checked: bool | None = None
    category: str | None = None


class ShoppingListItemResponse(BaseModel):
    """Response schema for a shopping list item."""

    id: str
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    is_checked: bool
    checked_by_user_id: str | None = None
    recipe_id: str | None = None
    already_have_quantity: Decimal | None = None
    category: str | None = None
    ingredient_id: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShoppingListCreate(BaseModel):
    """Request schema for creating a shopping list."""

    name: str | None = None
    meal_event_id: str | None = None
    pantry_id: str | None = None
    items: list[ShoppingListItemCreate] = []


class ShoppingListUpdate(BaseModel):
    """Request schema for updating a shopping list."""

    name: str | None = None
    status: str | None = None  # pending | in_progress | completed


class ShoppingListResponse(BaseModel):
    """Response schema for a shopping list with items."""

    id: str
    name: str | None = None
    status: str
    meal_event_id: str | None = None
    pantry_id: str | None = None
    owner_id: str
    items: list[ShoppingListItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShoppingListListItem(BaseModel):
    """Summary schema for a shopping list in a list view."""

    id: str
    name: str | None = None
    status: str
    meal_event_id: str | None = None
    item_count: int = 0
    checked_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ShoppingListListResponse(BaseModel):
    """Response schema for a paginated list of shopping lists."""

    items: list[ShoppingListListItem]
    total: int
    limit: int
    offset: int


class GenerateShoppingListRequest(BaseModel):
    """Request to generate a shopping list from a meal event."""

    check_pantry: bool = True  # Whether to check pantry for existing items
