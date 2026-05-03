"""Shopping list related Pydantic schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_serializer


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

    # Pydantic v2's default JSON mode renders Decimal as a string, which
    # breaks Dart's `as num?` cast on the client (see ErrorReporter
    # area=shopping.cart, operation=loadList — _TypeError "type 'String'
    # is not a subtype of type 'num?'"). Coerce to float so the wire
    # payload is a JSON number on both HTTP responses and WS broadcasts
    # (broadcasts re-encode via json.loads(result.body)).
    @field_serializer("quantity", "already_have_quantity")
    def _decimal_to_float(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None

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
    """Request to generate a shopping list from a meal event.

    Pantry cross-check was retired in
    epic-ingredients-string-simplification; the schema carries no fields
    and the endpoint rejects unknown fields (`extra="forbid"`) so stale
    clients sending `check_pantry` see a 422 rather than a silent 201.
    """

    model_config = {"extra": "forbid"}
