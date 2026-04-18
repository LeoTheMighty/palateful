"""Delete meal event endpoint."""

from datetime import UTC, datetime

from api.v1.calendar.dependencies import require_calendar_access
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.user import User


class DeleteMealEvent(Endpoint):
    """Delete (archive) a meal event.

    Calendar editor role (owner or editor) required. Non-members see a
    404 instead of 403 so we don't leak existence.
    """

    def execute(self, event_id: str):
        user: User = self.user

        meal_event = self.database.find_by(MealEvent, id=event_id)
        if not meal_event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        try:
            require_calendar_access(
                str(meal_event.calendar_id), user, self.database
            )
        except APIException as exc:
            if exc.status_code == 403:
                raise APIException(
                    status_code=404,
                    detail=f"Meal event with ID '{event_id}' not found",
                    code=ErrorCode.MEAL_EVENT_NOT_FOUND,
                ) from exc
            raise  # pragma: no cover — require_calendar_access only raises 403

        # Soft delete.
        meal_event.archived_at = datetime.now(UTC)
        self.database.db.commit()

        return success(data={"deleted": True, "id": str(event_id)})
