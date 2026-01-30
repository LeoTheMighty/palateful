"""User-related Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: str
    email: str
    name: str | None = None
    picture: str | None = None
    has_completed_onboarding: bool
    default_recipe_book_id: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecipeBookResponse(BaseModel):
    """Response schema for recipe book data."""
    id: str
    name: str
    description: str | None = None
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True


class OnboardingRequest(BaseModel):
    """Request schema for completing onboarding."""
    name: str
    start_method: Literal["browse", "import", "scratch"]


class OnboardingResponse(BaseModel):
    """Response schema for onboarding completion."""
    success: bool
    user: UserResponse | None = None
    recipe_book: RecipeBookResponse | None = None
    start_method: str | None = None
