"""Get active timers endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.active_timer import ActiveTimer
from utils.models.user import User


class GetActiveTimers(Endpoint):
    """Get all active timers for the current user."""

    def execute(self):
        """
        Get all active (running or paused) timers for the current user.

        Returns:
            List of active timers
        """
        user: User = self.user

        # Find active timers (running or paused)
        timers = (
            self.db.query(ActiveTimer)
            .filter(ActiveTimer.user_id == user.id)
            .filter(ActiveTimer.status.in_(["running", "paused"]))
            .filter(ActiveTimer.archived_at.is_(None))
            .order_by(ActiveTimer.created_at.desc())
            .all()
        )

        items = []
        for timer in timers:
            items.append(
                GetActiveTimers.TimerResponse(
                    id=str(timer.id),
                    label=timer.label,
                    duration_seconds=timer.duration_seconds,
                    status=timer.status,
                    started_at=timer.started_at,
                    paused_at=timer.paused_at,
                    elapsed_when_paused=timer.elapsed_when_paused,
                    notify_on_complete=timer.notify_on_complete,
                    notification_sent=timer.notification_sent,
                    remaining_seconds=timer.remaining_seconds,
                    is_expired=timer.is_expired,
                    user_id=str(timer.user_id),
                    meal_event_id=(
                        str(timer.meal_event_id) if timer.meal_event_id else None
                    ),
                    recipe_step_id=(
                        str(timer.recipe_step_id) if timer.recipe_step_id else None
                    ),
                    created_at=timer.created_at,
                    updated_at=timer.updated_at,
                )
            )

        return success(
            data=GetActiveTimers.Response(
                items=items,
                total=len(items),
            )
        )

    class TimerResponse(BaseModel):
        id: str
        label: str
        duration_seconds: int
        status: str
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

    class Response(BaseModel):
        items: list["GetActiveTimers.TimerResponse"]
        total: int
