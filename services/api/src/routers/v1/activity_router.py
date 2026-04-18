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
from fastapi import APIRouter, Depends, Query
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
):
    """List user's activity feed items."""
    return ListActivities.call(
        limit=limit,
        offset=offset,
        include_archived=include_archived,
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
