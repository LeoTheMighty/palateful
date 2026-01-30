"""Timer endpoints router."""

from api.v1.timer import (
    CreateTimer,
    DeleteTimer,
    GetActiveTimers,
    UpdateTimer,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

timer_router = APIRouter(tags=["timers"])


@timer_router.get("/timers/active")
async def get_active_timers(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get all active timers for the current user."""
    return GetActiveTimers.call(
        user=user,
        database=database,
    )


@timer_router.post("/timers")
async def create_timer(
    params: CreateTimer.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a new timer."""
    return CreateTimer.call(
        params=params,
        user=user,
        database=database,
    )


@timer_router.put("/timers/{timer_id}")
async def update_timer(
    timer_id: str,
    params: UpdateTimer.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a timer (pause, resume, add time, complete, cancel)."""
    return UpdateTimer.call(
        timer_id=timer_id,
        params=params,
        user=user,
        database=database,
    )


@timer_router.delete("/timers/{timer_id}")
async def delete_timer(
    timer_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Delete (cancel) a timer."""
    return DeleteTimer.call(
        timer_id=timer_id,
        user=user,
        database=database,
    )
