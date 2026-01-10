"""User endpoints."""

import secrets

from fastapi import APIRouter

from utils.models.user import User
from dependencies import get_database

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/{user_id}", response_model=GetUser.Response)
async def get_user(user_id: str, database: Database = Depends(get_database)):
    """Get user by ID."""
    return GetUser.call(
        user_id,
        database=database
    )


@user_router.post("", response_model=CreateUser.Response)
@user_router.post("/", response_model=CreateUser.Response)
async def create_user(params: CreateUser.Params, database: Database = Depends(get_database)):
    """Create a new user."""
    return CreateUser.call(
        params,
        database=database
    )


@user_router.post("/me/complete-onboarding", response_model=OnboardingResponse)
async def complete_onboarding(db: DbSession, user: CurrentUser):
    """Mark user's onboarding as complete."""
    user.has_completed_onboarding = True
    await db.commit()
    return OnboardingResponse(success=True)


@users_router.post("/register", response_model=UserResponse)
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
