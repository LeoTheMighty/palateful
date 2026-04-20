"""Pydantic schemas for pantry endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

StorageLocation = Literal["fridge", "pantry", "freezer"]


class PantryIngredientRead(BaseModel):
    """Representation of a pantry ingredient row."""

    pantry_id: str
    ingredient_id: str
    ingredient_name: str | None = None
    category: str | None = None
    quantity_display: Decimal
    unit_display: str
    quantity_normalized: Decimal
    unit_normalized: str
    storage_location: StorageLocation | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class PantryRead(BaseModel):
    """A pantry plus its active ingredients."""

    id: str
    name: str
    role: str
    items: list[PantryIngredientRead]


class PantryIngredientCreate(BaseModel):
    """Input body for creating/upserting a pantry ingredient.

    Exactly one of `ingredient_id` or `name` must be supplied. `name`
    creates a fresh `ingredients` row inline (no find-or-create — see
    `epic-ingredients-string-simplification`); `ingredient_id` preserves
    the FK of an existing row.
    """

    ingredient_id: str | None = None
    name: str | None = None
    quantity_display: Decimal
    unit_display: str
    quantity_normalized: Decimal
    unit_normalized: str
    storage_location: StorageLocation | None = None
    expires_at: datetime | None = None


class PantryIngredientUpdate(BaseModel):
    """Input body for updating a pantry ingredient."""

    quantity_display: Decimal | None = None
    unit_display: str | None = None
    quantity_normalized: Decimal | None = None
    unit_normalized: str | None = None
    storage_location: StorageLocation | None = None
    expires_at: datetime | None = None
