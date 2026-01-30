"""Recipe book-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class RecipeBookCreate(BaseModel):
    """Request schema for creating a recipe book."""
    name: str
    description: str | None = None


class RecipeBookUpdate(BaseModel):
    """Request schema for updating a recipe book."""
    name: str | None = None
    description: str | None = None


class RecipeBookResponse(BaseModel):
    """Response schema for a recipe book."""
    id: str
    name: str
    description: str | None = None
    recipe_count: int = 0
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


class RecipeBookDetailResponse(BaseModel):
    """Response schema for a recipe book with recipes."""
    id: str
    name: str
    description: str | None = None
    recipe_count: int = 0
    recipes: list[RecipeListItem] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeBookListResponse(BaseModel):
    """Response schema for a paginated list of recipe books."""
    items: list[RecipeBookResponse]
    total: int
    limit: int
    offset: int
