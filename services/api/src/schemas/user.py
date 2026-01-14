"""User-related Pydantic schemas."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    has_completed_onboarding: bool
    default_recipe_book_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecipeBookResponse(BaseModel):
    """Response schema for recipe book data."""
    id: str
    name: str
    description: Optional[str] = None
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
    user: Optional[UserResponse] = None
    recipe_book: Optional[RecipeBookResponse] = None
    start_method: Optional[str] = None
