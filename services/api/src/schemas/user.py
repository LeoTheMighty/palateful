"""User schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    name: str | None = None
    picture: str | None = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    auth0_id: str


class UserResponse(UserBase):
    """Schema for user responses."""

    id: str
    email_verified: bool
    has_completed_onboarding: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OnboardingResponse(BaseModel):
    """Response for completing onboarding."""

    success: bool
