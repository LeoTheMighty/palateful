"""Calendar endpoints router."""

from api.v1.calendar import (
    CreateCalendar,
    DeleteCalendar,
    GetCalendar,
    ListCalendars,
    UpdateCalendar,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

calendar_router = APIRouter(prefix="/calendars", tags=["calendars"])


@calendar_router.get("")
async def list_calendars(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List all calendars the user is an active member of."""
    return ListCalendars.call(user=user, database=database)


@calendar_router.post("")
async def create_calendar(
    params: CreateCalendar.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a new calendar owned by the authenticated user."""
    return CreateCalendar.call(params, user=user, database=database)


@calendar_router.get("/{calendar_id}")
async def get_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get a single calendar plus its members."""
    return GetCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )


@calendar_router.patch("/{calendar_id}")
async def update_calendar(
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
async def delete_calendar(
    calendar_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Archive a calendar (soft-delete)."""
    return DeleteCalendar.call(
        calendar_id=calendar_id, user=user, database=database
    )
