"""User endpoints router."""

from fastapi import APIRouter, Depends, Header

from dependencies import get_database, get_current_user
from schemas.user import OnboardingRequest
from utils.models.user import User
from utils.services.database import Database
from api.v1.user import GetMe, CompleteOnboarding


user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    authorization: str = Header(None),
    database=Depends(get_database)
):
    """Get the current authenticated user."""
    return GetMe.call(user=user, database=database)


@user_router.post("/me/complete-onboarding")
async def complete_onboarding(
    params: OnboardingRequest,
    user: User = Depends(get_current_user),
    authorization: str = Header(None),
    database: Database = Depends(get_database)
):
    """Complete user onboarding with name and start method."""
    return CompleteOnboarding.call(params, user=user, database=database)
