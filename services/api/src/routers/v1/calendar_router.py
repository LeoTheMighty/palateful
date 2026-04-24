"""Calendar endpoints router.

aam-14: flipped to `get_async_database` + `get_current_user_async`.
Every endpoint dispatches through `await Foo.call(...)` on an
`AsyncEndpoint` subclass. `_ensure_default_calendar` stays sync —
`get_current_user_async` already runs it inside the async auth dep
via threadpool.
"""

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
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

calendar_router = APIRouter(prefix="/calendars", tags=["calendars"])


@calendar_router.get("")
async def list_calendars(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List all calendars the user is an active member of."""
    return await ListCalendars.call(user=user, database=database)


@calendar_router.post("")
async def create_calendar(
    params: CreateCalendar.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Create a new calendar owned by the authenticated user."""
    return await CreateCalendar.call(params, user=user, database=database)


@calendar_router.get("/{calendar_id}")
async def get_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get a single calendar plus its members."""
    return await GetCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )


@calendar_router.patch("/{calendar_id}")
async def update_calendar(
    calendar_id: str,
    params: UpdateCalendar.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Update a calendar's name or description (owner-only)."""
    return await UpdateCalendar.call(
        calendar_id=calendar_id, params=params, user=user, database=database
    )


@calendar_router.delete("/{calendar_id}")
async def delete_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Archive a calendar (soft-delete)."""
    return await DeleteCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )


@calendar_router.get("/{calendar_id}/members")
async def list_calendar_members(
    calendar_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List active members + pending invitations for a calendar."""
    return await ListCalendarMembers.call(
        calendar_id=calendar_id, user=user, database=database
    )


@calendar_router.patch("/{calendar_id}/members/{target_user_id}")
async def update_calendar_member(
    calendar_id: str,
    target_user_id: str,
    params: UpdateCalendarMember.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Change a member's role — owner-only. Promote-to-owner transfers atomically."""
    return await UpdateCalendarMember.call(
        calendar_id=calendar_id,
        target_user_id=target_user_id,
        params=params,
        user=user,
        database=database,
    )


@calendar_router.delete("/{calendar_id}/members/{target_user_id}")
async def remove_calendar_member(
    calendar_id: str,
    target_user_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Remove a member from a calendar — owner-only."""
    return await RemoveCalendarMember.call(
        calendar_id=calendar_id,
        target_user_id=target_user_id,
        user=user,
        database=database,
    )


@calendar_router.post("/{calendar_id}/leave")
async def leave_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Leave a calendar (caller's own row archived). Owners cannot leave."""
    return await LeaveCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )
