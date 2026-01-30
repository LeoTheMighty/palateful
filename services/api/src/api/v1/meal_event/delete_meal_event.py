"""Delete meal event endpoint."""

from datetime import datetime

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.user import User


class DeleteMealEvent(Endpoint):
    """Delete (archive) a meal event."""

    def execute(self, event_id: str):
        """
        Delete (archive) a meal event.

        Args:
            event_id: The meal event's ID

        Returns:
            Success acknowledgment
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

        # Check access - only owner can delete
        if meal_event.owner_id != user.id:
            raise APIException(
                status_code=403,
                detail="Only the owner can delete this meal event",
                code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
            )

        # Soft delete by setting archived_at
        meal_event.archived_at = datetime.utcnow()
        self.database.db.commit()

        return success(data={"deleted": True, "id": str(event_id)})
