"""User endpoints router.

aam-19: remaining sync handlers (profile, defaults, onboarding,
push-tokens, username, export, search) flipped to `async def` with
`get_current_user_async` + `get_async_database`. The feedback,
client-errors, and notification-preferences handlers (flipped in aam-21)
stay async; no sync handlers remain on this router.
"""

from api.v1.user import (
    CheckUsername,
    CompleteOnboarding,
    CreateUserFeedback,
    ExportRecipes,
    GetMe,
    GetNotificationPreferences,
    RecordClientError,
    RegisterPushToken,
    SearchUsers,
    SetDefaultRecipeBook,
    SetDefaultShoppingList,
    SetUsername,
    UnregisterPushToken,
    UpdateMe,
    UpdateNotificationPreferences,
)
from dependencies import (
    get_async_database,
    get_current_user_async,
)
from fastapi import APIRouter, Depends, Header, Query
from schemas.user import OnboardingRequest
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/me")
async def get_me(
    user: User = Depends(get_current_user_async),
    authorization: str = Header(None),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get the current authenticated user."""
    return await GetMe.call(user=user, database=database)


@user_router.put("/me")
async def update_me(
    params: UpdateMe.Params,
    user: User = Depends(get_current_user_async),
    authorization: str = Header(None),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Update the current user's profile."""
    return await UpdateMe.call(params, user=user, database=database)


@user_router.put("/me/default-recipe-book")
async def set_default_recipe_book(
    params: SetDefaultRecipeBook.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Set the user's default recipe book."""
    return await SetDefaultRecipeBook.call(params=params, user=user, database=database)


@user_router.put("/me/default-shopping-list")
async def set_default_shopping_list(
    params: SetDefaultShoppingList.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Set the user's default shopping list."""
    return await SetDefaultShoppingList.call(params=params, user=user, database=database)


@user_router.post("/me/complete-onboarding")
async def complete_onboarding(
    params: OnboardingRequest,
    user: User = Depends(get_current_user_async),
    authorization: str = Header(None),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Complete user onboarding with name and start method."""
    return await CompleteOnboarding.call(params, user=user, database=database)


# ============================================================
# Push Notification Token Management
# ============================================================


@user_router.post("/me/push-tokens")
async def register_push_token(
    params: RegisterPushToken.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Register a device push notification token."""
    return await RegisterPushToken.call(params=params, user=user, database=database)


@user_router.delete("/me/push-tokens")
async def unregister_push_token(
    params: UnregisterPushToken.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Unregister a device push notification token."""
    return await UnregisterPushToken.call(params=params, user=user, database=database)


@user_router.post("/me/client-errors")
async def record_client_error(
    params: RecordClientError.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Record a client-side error/breadcrumb as an error_logs row with service='client'.

    aam-21 hot-path flip: baseline server-side p95 was 5931 ms; target
    is < 200 ms once the async write path settles. The write itself is
    a single INSERT — the latency came from event-loop contention,
    not query cost.
    """
    return await RecordClientError.call(
        params=params, user=user, database=database
    )


@user_router.get("/me/notification-preferences")
async def get_notification_preferences(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get notification preferences."""
    return await GetNotificationPreferences.call(user=user, database=database)


@user_router.put("/me/notification-preferences")
async def update_notification_preferences(
    params: UpdateNotificationPreferences.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Update notification preferences."""
    return await UpdateNotificationPreferences.call(
        params=params, user=user, database=database
    )


# ============================================================
# Username Management
# ============================================================


@user_router.put("/me/username")
async def set_username(
    params: SetUsername.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Set or update the current user's username."""
    return await SetUsername.call(params=params, user=user, database=database)


@user_router.get("/check-username/{username}")
async def check_username(
    username: str,
    database: AsyncDatabase = Depends(get_async_database),
):
    """Check if a username is available."""
    return await CheckUsername.call(username=username, database=database)


# ============================================================
# Data Export
# ============================================================


@user_router.get("/me/export")
async def export_recipes(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Export the user's entire recipe collection as JSON."""
    return await ExportRecipes.call(user=user, database=database)


# ============================================================
# User Search
# ============================================================


@user_router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Search for users by username or name."""
    return await SearchUsers.call(q=q, limit=limit, user=user, database=database)


# ============================================================
# User Feedback
# ============================================================


@user_router.post("/me/feedback")
async def create_user_feedback(
    params: CreateUserFeedback.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Submit user feedback to the admin inbox."""
    return await CreateUserFeedback.call(
        params=params, user=user, database=database
    )
