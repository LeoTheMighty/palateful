"""Activity feed endpoints router."""

from api.v1.user_activity import (
    ArchiveActivity,
    ListActivities,
    MarkActivityRead,
    MarkAllRead,
    UnarchiveActivity,
    UnreadCount,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, HTTPException, Query
from utils.models.user import User
from utils.services.database import Database

activity_router = APIRouter(prefix="/activities", tags=["activities"])


@activity_router.get("")
async def list_activities(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
    limit: int = 50,
    offset: int = 0,
    include_archived: bool = Query(
        False, description="Include archived activities"
    ),
    include_system_types: bool = Query(
        False,
        description=(
            "Admin-only debug flag. When true, returns all user_activity "
            "types (including import_* rows) instead of the default "
            "Notifications-tab allow-list. Non-admin callers passing this "
            "flag get 403."
        ),
    ),
    include_read: bool = Query(
        False,
        description=(
            "When true, includes read-but-not-archived rows in the "
            "result. Combined with include_archived=true and "
            "since_days= (empty), powers the See-all footer."
        ),
    ),
    since_days: str | None = Query(
        "30",
        description=(
            "Window (days) for created_at cutoff. Default 30. Pass an "
            "empty value (?since_days=) to opt out of the window — the "
            "See-all footer uses this."
        ),
    ),
    cursor: str | None = Query(
        None,
        description=(
            "Opaque cursor from a prior page's next_cursor. Mutually "
            "exclusive with offset — both-present returns 400."
        ),
    ),
):
    """List user's activity feed items."""
    # ``since_days=`` (empty) is the explicit opt-out of the retention
    # window per afh-1a AC3. Pydantic Int coercion rejects ``""``, so
    # the router accepts a string and parses it here.
    parsed_since_days: int | None
    if since_days is None or since_days == "":
        parsed_since_days = None
    else:
        try:
            parsed_since_days = int(since_days)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="since_days must be an integer or empty"
            ) from exc
    return ListActivities.call(
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        include_system_types=include_system_types,
        include_read=include_read,
        since_days=parsed_since_days,
        cursor=cursor,
        user=user,
        database=database,
    )


@activity_router.get("/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get count of unread activities for badge display."""
    return UnreadCount.call(user=user, database=database)


@activity_router.put("/{activity_id}/read")
async def mark_activity_read(
    activity_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Mark a single activity as read."""
    return MarkActivityRead.call(
        activity_id=activity_id,
        user=user,
        database=database,
    )


@activity_router.put("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Mark all user activities as read."""
    return MarkAllRead.call(user=user, database=database)


@activity_router.post("/{activity_id}/archive")
async def archive_activity(
    activity_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Archive a single activity (hide from default feed, keep in See-all)."""
    return ArchiveActivity.call(
        activity_id=activity_id,
        user=user,
        database=database,
    )


@activity_router.post("/{activity_id}/unarchive")
async def unarchive_activity(
    activity_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Restore an archived activity to the default feed."""
    return UnarchiveActivity.call(
        activity_id=activity_id,
        user=user,
        database=database,
    )
