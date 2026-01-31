"""User endpoints router."""

from api.v1.user import (
    CheckUsername,
    CompleteOnboarding,
    GetMe,
    GetNotificationPreferences,
    RegisterPushToken,
    SearchUsers,
    SetUsername,
    UnregisterPushToken,
    UpdateNotificationPreferences,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, Header, Query
from schemas.user import OnboardingRequest
from utils.models.user import User
from utils.services.database import Database

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    authorization: str = Header(None),
    database=Depends(get_database),
):
    """Get the current authenticated user."""
    return GetMe.call(user=user, database=database)


@user_router.post("/me/complete-onboarding")
async def complete_onboarding(
    params: OnboardingRequest,
    user: User = Depends(get_current_user),
    authorization: str = Header(None),
    database: Database = Depends(get_database),
):
    """Complete user onboarding with name and start method."""
    return CompleteOnboarding.call(params, user=user, database=database)


# ============================================================
# Push Notification Token Management
# ============================================================


@user_router.post("/me/push-tokens")
async def register_push_token(
    params: RegisterPushToken.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Register a device push notification token."""
    return RegisterPushToken.call(params=params, user=user, database=database)


@user_router.delete("/me/push-tokens")
async def unregister_push_token(
    params: UnregisterPushToken.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Unregister a device push notification token."""
    return UnregisterPushToken.call(params=params, user=user, database=database)


@user_router.get("/me/notification-preferences")
async def get_notification_preferences(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get notification preferences."""
    return GetNotificationPreferences.call(user=user, database=database)


@user_router.put("/me/notification-preferences")
async def update_notification_preferences(
    params: UpdateNotificationPreferences.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update notification preferences."""
    return UpdateNotificationPreferences.call(
        params=params, user=user, database=database
    )


# ============================================================
# Username Management
# ============================================================


@user_router.put("/me/username")
async def set_username(
    params: SetUsername.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Set or update the current user's username."""
    return SetUsername.call(params=params, user=user, database=database)


@user_router.get("/check-username/{username}")
async def check_username(
    username: str,
    database: Database = Depends(get_database),
):
    """Check if a username is available."""
    return CheckUsername.call(username=username, database=database)


# ============================================================
# User Search
# ============================================================


@user_router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Search for users by username or name."""
    return SearchUsers.call(q=q, limit=limit, user=user, database=database)
