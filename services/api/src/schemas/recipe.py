"""Recipe-related Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class RecipeIngredientInput(BaseModel):
    """Input schema for a recipe ingredient."""
    ingredient_id: str
    quantity: Decimal
    unit: str
    notes: Optional[str] = None
    is_optional: bool = False


class IngredientSummary(BaseModel):
    """Summary of ingredient for display."""
    id: str
    canonical_name: str
    category: Optional[str] = None

    class Config:
        from_attributes = True


class RecipeIngredientResponse(BaseModel):
    """Response schema for a recipe ingredient."""
    id: str
    ingredient: IngredientSummary
    quantity_display: Decimal
    unit_display: str
    quantity_normalized: Optional[Decimal] = None
    unit_normalized: Optional[str] = None
    notes: Optional[str] = None
    is_optional: bool = False
    order_index: int = 0

    class Config:
        from_attributes = True


class RecipeCreate(BaseModel):
    """Request schema for creating a recipe."""
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    servings: int = 1
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    ingredients: list[RecipeIngredientInput] = []


class RecipeUpdate(BaseModel):
    """Request schema for updating a recipe."""
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    servings: Optional[int] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    ingredients: Optional[list[RecipeIngredientInput]] = None


class RecipeResponse(BaseModel):
    """Response schema for a recipe with full details."""
    id: str
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    servings: int = 1
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    ingredients: list[RecipeIngredientResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeListItem(BaseModel):
    """Summary schema for a recipe in a list."""
    id: str
    name: str
    description: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    servings: Optional[int] = None
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecipeListResponse(BaseModel):
    """Response schema for a paginated list of recipes."""
    items: list[RecipeListItem]
    total: int
    limit: int
    offset: int
