"""Recipe-related Pydantic schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RecipeIngredientInput(BaseModel):
    """Input schema for a recipe ingredient."""
    ingredient_id: str
    quantity: Decimal
    unit: str
    notes: str | None = None
    is_optional: bool = False


class IngredientSummary(BaseModel):
    """Summary of ingredient for display."""
    id: str
    canonical_name: str
    category: str | None = None

    class Config:
        from_attributes = True


class RecipeIngredientResponse(BaseModel):
    """Response schema for a recipe ingredient."""
    id: str
    ingredient: IngredientSummary
    quantity_display: Decimal
    unit_display: str
    quantity_normalized: Decimal | None = None
    unit_normalized: str | None = None
    notes: str | None = None
    is_optional: bool = False
    order_index: int = 0

    class Config:
        from_attributes = True


class RecipeCreate(BaseModel):
    """Request schema for creating a recipe."""
    name: str
    description: str | None = None
    instructions: str | None = None
    servings: int = 1
    prep_time: int | None = None
    cook_time: int | None = None
    image_url: str | None = None
    source_url: str | None = None
    ingredients: list[RecipeIngredientInput] = []


class RecipeUpdate(BaseModel):
    """Request schema for updating a recipe."""
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    servings: int | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    image_url: str | None = None
    source_url: str | None = None
    ingredients: list[RecipeIngredientInput] | None = None


class RecipeResponse(BaseModel):
    """Response schema for a recipe with full details."""
    id: str
    name: str
    description: str | None = None
    instructions: str | None = None
    servings: int = 1
    prep_time: int | None = None
    cook_time: int | None = None
    image_url: str | None = None
    source_url: str | None = None
    ingredients: list[RecipeIngredientResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeListItem(BaseModel):
    """Summary schema for a recipe in a list."""
    id: str
    name: str
    description: str | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    servings: int | None = None
    image_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecipeListResponse(BaseModel):
    """Response schema for a paginated list of recipes."""
    items: list[RecipeListItem]
    total: int
    limit: int
    offset: int
