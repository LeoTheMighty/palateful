"""Ingredient-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class IngredientCreate(BaseModel):
    """Request schema for creating an ingredient."""
    canonical_name: str
    category: str | None = None
    default_unit: str | None = None


class IngredientSearchItem(BaseModel):
    """Response schema for an ingredient search result."""
    id: str
    canonical_name: str
    category: str | None = None
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
    category: str | None = None
    flavor_profile: list[str] = []
    default_unit: str | None = None
    is_canonical: bool = True
    pending_review: bool = False
    image_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
