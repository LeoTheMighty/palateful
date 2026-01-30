"""Timer related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class TimerCreate(BaseModel):
    """Request schema for creating a timer."""

    label: str
    duration_seconds: int
    meal_event_id: str | None = None
    recipe_step_id: str | None = None
    notify_on_complete: bool = True


class TimerUpdate(BaseModel):
    """Request schema for updating a timer."""

    status: str | None = None  # running | paused | completed | cancelled
    # For adding time while running/paused
    add_seconds: int | None = None


class TimerResponse(BaseModel):
    """Response schema for a timer."""

    id: str
    label: str
    duration_seconds: int
    status: str  # running | paused | completed | cancelled
    started_at: datetime
    paused_at: datetime | None = None
    elapsed_when_paused: int
    notify_on_complete: bool
    notification_sent: bool
    remaining_seconds: int
    is_expired: bool
    user_id: str
    meal_event_id: str | None = None
    recipe_step_id: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimerListResponse(BaseModel):
    """Response schema for a list of timers."""

    items: list[TimerResponse]
    total: int
