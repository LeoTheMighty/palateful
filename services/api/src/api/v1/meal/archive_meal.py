"""POST /v1/meals/{meal_id}/archive — soft-archive a Meal."""

from datetime import UTC, datetime

from api.v1.meal._access import require_meal_write
from schemas.meal import MealArchiveResponse
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.error_log import ErrorLog
from utils.models.user import User


class ArchiveMeal(AsyncEndpoint):
    """Soft-archive a Meal. Idempotent — already-archived → 400."""

    async def execute(self, meal_id: str):
        user: User = self.user
        db = self.db

        meal = await require_meal_write(db, meal_id, user)
        if meal.archived_at is not None:
            raise APIException(
                status_code=400,
                detail="Meal is already archived",
                code=ErrorCode.MEAL_ALREADY_ARCHIVED,
            )

        meal.archived_at = datetime.now(UTC)

        audit = ErrorLog(
            error_type="MealArchive",
            error_message=(
                f"Meal {meal.id} ('{meal.name}') archived by user {user.id}"
            ),
            service="audit",
            user_id=user.id,
        )
        await self.database.create(audit)

        await db.flush()
        await db.commit()
        return success(
            data=MealArchiveResponse(success=True, archived_at=meal.archived_at)
        )
