"""Calendar endpoints router."""

from api.v1.calendar import (
    CreateCalendar,
    DeleteCalendar,
    GetCalendar,
    LeaveCalendar,
    ListCalendarMembers,
    ListCalendars,
    RemoveCalendarMember,
    UpdateCalendar,
    UpdateCalendarMember,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

calendar_router = APIRouter(prefix="/calendars", tags=["calendars"])


@calendar_router.get("")
def list_calendars(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List all calendars the user is an active member of."""
    return ListCalendars.call(user=user, database=database)


@calendar_router.post("")
def create_calendar(
    params: CreateCalendar.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a new calendar owned by the authenticated user."""
    return CreateCalendar.call(params, user=user, database=database)


@calendar_router.get("/{calendar_id}")
def get_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get a single calendar plus its members."""
    return GetCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )


@calendar_router.patch("/{calendar_id}")
def update_calendar(
    calendar_id: str,
    params: UpdateCalendar.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a calendar's name or description (owner-only)."""
    return UpdateCalendar.call(
        calendar_id=calendar_id, params=params, user=user, database=database
    )


@calendar_router.delete("/{calendar_id}")
def delete_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Archive a calendar (soft-delete)."""
    return DeleteCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )


@calendar_router.get("/{calendar_id}/members")
def list_calendar_members(
    calendar_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List active members + pending invitations for a calendar."""
    return ListCalendarMembers.call(
        calendar_id=calendar_id, user=user, database=database
    )


@calendar_router.patch("/{calendar_id}/members/{target_user_id}")
def update_calendar_member(
    calendar_id: str,
    target_user_id: str,
    params: UpdateCalendarMember.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Change a member's role — owner-only. Promote-to-owner transfers atomically."""
    return UpdateCalendarMember.call(
        calendar_id=calendar_id,
        target_user_id=target_user_id,
        params=params,
        user=user,
        database=database,
    )


@calendar_router.delete("/{calendar_id}/members/{target_user_id}")
def remove_calendar_member(
    calendar_id: str,
    target_user_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Remove a member from a calendar — owner-only."""
    return RemoveCalendarMember.call(
        calendar_id=calendar_id,
        target_user_id=target_user_id,
        user=user,
        database=database,
    )


@calendar_router.post("/{calendar_id}/leave")
def leave_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Leave a calendar (caller's own row archived). Owners cannot leave."""
    return LeaveCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )
