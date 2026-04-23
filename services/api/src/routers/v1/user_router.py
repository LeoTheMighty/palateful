"""User endpoints router.

aam-21 partial flip: `feedback`, `client-errors`, and
`notification-preferences` endpoints now depend on the async auth +
DB deps and dispatch through `await Foo.call(...)`. The rest of the
router (profile, push-tokens, search, onboarding, export) stays sync
— aam-19 owns that conversion.
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
    get_current_user,
    get_current_user_async,
    get_database,
)
from fastapi import APIRouter, Depends, Header, Query
from schemas.user import OnboardingRequest
from utils.models.user import User
from utils.services.async_database import AsyncDatabase
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


@user_router.put("/me")
async def update_me(
    params: UpdateMe.Params,
    user: User = Depends(get_current_user),
    authorization: str = Header(None),
    database: Database = Depends(get_database),
):
    """Update the current user's profile."""
    return UpdateMe.call(params, user=user, database=database)


@user_router.put("/me/default-recipe-book")
async def set_default_recipe_book(
    params: SetDefaultRecipeBook.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Set the user's default recipe book."""
    return SetDefaultRecipeBook.call(params=params, user=user, database=database)


@user_router.put("/me/default-shopping-list")
async def set_default_shopping_list(
    params: SetDefaultShoppingList.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Set the user's default shopping list."""
    return SetDefaultShoppingList.call(params=params, user=user, database=database)


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
# Data Export
# ============================================================


@user_router.get("/me/export")
async def export_recipes(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Export the user's entire recipe collection as JSON."""
    return ExportRecipes.call(user=user, database=database)


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
