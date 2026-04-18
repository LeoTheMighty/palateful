"""User-related Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: str
    email: str | None = None
    name: str | None = None
    username: str | None = None
    picture: str | None = None
    has_completed_onboarding: bool
    default_recipe_book_id: str | None = None
    previous_recipe_book_id: str | None = None
    default_shopping_list_id: str | None = None
    previous_shopping_list_id: str | None = None
    created_at: datetime
    username_changed_at: datetime | None = None
    pending_invitation_count: int = 0

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
    # Recorded during the onboarding notification step (notif-4). Reflects
    # the OS AuthorizationStatus, not which button the user tapped. None
    # means the client didn't supply it (older builds / web).
    notification_permission_status: Literal[
        "granted", "provisional", "declined"
    ] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v.strip()) > 100:
            raise ValueError("Name must be at most 100 characters")
        return v


class OnboardingResponse(BaseModel):
    """Response schema for onboarding completion."""
    success: bool
    user: UserResponse | None = None
    recipe_book: RecipeBookResponse | None = None
    start_method: str | None = None
