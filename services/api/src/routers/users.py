"""User endpoints."""

import secrets

from fastapi import APIRouter

from palateful_utils.db.models import User
from src.dependencies import CurrentUser, CurrentUserId, DbSession
from src.schemas.user import OnboardingResponse, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(user: CurrentUser):
    """Get current user's profile."""
    return user


@router.post("/me/complete-onboarding", response_model=OnboardingResponse)
async def complete_onboarding(db: DbSession, user: CurrentUser):
    """Mark user's onboarding as complete."""
    user.has_completed_onboarding = True
    await db.commit()
    return OnboardingResponse(success=True)


@router.post("/register", response_model=UserResponse)
async def register_or_get_user(
    db: DbSession,
    auth0_id: CurrentUserId,
):
    """
    Register a new user or return existing user.
    Called after Auth0 login to ensure user exists in database.
    """
    from sqlalchemy import select

    # Check if user exists
    result = await db.execute(select(User).where(User.auth0_id == auth0_id))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return existing_user

    # Create new user
    # Note: In production, you'd get email/name from Auth0 userinfo endpoint
    new_user = User(
        id=secrets.token_urlsafe(16),
        auth0_id=auth0_id,
        email=f"{auth0_id.replace('|', '_')}@placeholder.local",  # Placeholder
        name=None,
        email_verified=False,
        has_completed_onboarding=False,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user
