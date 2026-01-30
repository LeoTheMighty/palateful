"""Update timer endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.active_timer import ActiveTimer
from utils.models.user import User

VALID_STATUSES = ["running", "paused", "completed", "cancelled"]


class UpdateTimer(Endpoint):
    """Update a timer (pause, resume, add time, complete, cancel)."""

    def execute(self, timer_id: str, params: "UpdateTimer.Params"):
        """
        Update a timer.

        Args:
            timer_id: The timer's ID
            params: Update parameters

        Returns:
            Updated timer data
        """
        user: User = self.user

        # Find timer
        timer = self.database.find_by(ActiveTimer, id=timer_id)
        if not timer or timer.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Timer with ID '{timer_id}' not found",
                code=ErrorCode.TIMER_NOT_FOUND,
            )

        # Check access
        if timer.user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You don't have permission to update this timer",
                code=ErrorCode.FORBIDDEN,
            )

        # Validate status if provided
        if params.status and params.status not in VALID_STATUSES:
            raise APIException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
                code=ErrorCode.TIMER_INVALID_STATUS,
            )

        # Handle status changes
        if params.status:
            if timer.status in ("completed", "cancelled"):
                raise APIException(
                    status_code=400,
                    detail="Cannot update a completed or cancelled timer",
                    code=ErrorCode.TIMER_ALREADY_COMPLETED,
                )

            if params.status == "paused" and timer.status == "running":
                # Pause the timer
                now = datetime.now(tz=UTC)
                elapsed = (now - timer.started_at).total_seconds()
                timer.elapsed_when_paused += int(elapsed)
                timer.paused_at = now
                timer.status = "paused"

            elif params.status == "running" and timer.status == "paused":
                # Resume the timer
                timer.started_at = datetime.now(tz=UTC)
                timer.paused_at = None
                timer.status = "running"

            elif params.status in ("completed", "cancelled"):
                timer.status = params.status

        # Add time if requested
        if params.add_seconds and params.add_seconds > 0:
            timer.duration_seconds += params.add_seconds

        self.database.db.commit()
        self.database.db.refresh(timer)

        return success(
            data=UpdateTimer.Response(
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

    class Params(BaseModel):
        status: str | None = None  # running | paused | completed | cancelled
        add_seconds: int | None = None  # Add time while running/paused

    class Response(BaseModel):
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
