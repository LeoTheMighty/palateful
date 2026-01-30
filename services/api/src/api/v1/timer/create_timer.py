"""Create timer endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.active_timer import ActiveTimer
from utils.models.user import User


class CreateTimer(Endpoint):
    """Create a new timer."""

    def execute(self, params: "CreateTimer.Params"):
        """
        Create a new cooking timer.

        Args:
            params: Timer creation parameters

        Returns:
            Created timer data
        """
        user: User = self.user

        # Create timer
        timer = ActiveTimer(
            label=params.label,
            duration_seconds=params.duration_seconds,
            status="running",
            started_at=datetime.now(tz=UTC),
            notify_on_complete=params.notify_on_complete,
            user_id=user.id,
            meal_event_id=params.meal_event_id,
            recipe_step_id=params.recipe_step_id,
        )
        self.database.create(timer)
        self.database.db.refresh(timer)

        return success(
            data=CreateTimer.Response(
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
            ),
            status=201,
        )

    class Params(BaseModel):
        label: str
        duration_seconds: int
        meal_event_id: str | None = None
        recipe_step_id: str | None = None
        notify_on_complete: bool = True

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
