"""Skip meal event endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.user import User


class SkipMealEvent(Endpoint):
    """Skip a meal event (mark as skipped to dismiss notifications)."""

    def execute(self, event_id: str):
        """
        Skip a meal event.

        Args:
            event_id: The meal event's ID

        Returns:
            Updated meal event status
        """
        user: User = self.user

        # Find meal event
        meal_event = self.database.find_by(MealEvent, id=event_id)
        if not meal_event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        # Check access - must be owner or cohost
        is_owner = meal_event.owner_id == user.id
        participant = self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=user.id
        )
        is_cohost = participant and participant.role in ("host", "cohost")
        if not is_owner and not is_cohost:
            raise APIException(
                status_code=403,
                detail="You don't have permission to skip this meal event",
                code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
            )

        # Update status to skipped
        meal_event.status = "skipped"
        self.database.db.commit()

        return success(
            data=SkipMealEvent.Response(
                id=str(meal_event.id),
                title=meal_event.title,
                status=meal_event.status,
                scheduled_at=meal_event.scheduled_at,
            )
        )

    class Response(BaseModel):
        id: str
        title: str
        status: str
        scheduled_at: datetime
