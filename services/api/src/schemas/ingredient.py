"""Ingredient-related Pydantic schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class IngredientCreate(BaseModel):
    """Request schema for creating an ingredient."""
    canonical_name: str
    category: Optional[str] = None
    default_unit: Optional[str] = None


class IngredientSearchItem(BaseModel):
    """Response schema for an ingredient search result."""
    id: str
    canonical_name: str
    category: Optional[str] = None
    similarity: float

    class Config:
        from_attributes = True


class IngredientSearchResponse(BaseModel):
    """Response schema for ingredient search results."""
    items: list[IngredientSearchItem]


class IngredientResponse(BaseModel):
    """Response schema for full ingredient details."""
    id: str
    canonical_name: str
    aliases: list[str] = []
    category: Optional[str] = None
    flavor_profile: list[str] = []
    default_unit: Optional[str] = None
    is_canonical: bool = True
    pending_review: bool = False
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
