"""Delete timer endpoint."""

from datetime import datetime

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.active_timer import ActiveTimer
from utils.models.user import User


class DeleteTimer(Endpoint):
    """Delete (cancel and archive) a timer."""

    def execute(self, timer_id: str):
        """
        Delete (cancel and archive) a timer.

        Args:
            timer_id: The timer's ID

        Returns:
            Success acknowledgment
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
                detail="You don't have permission to delete this timer",
                code=ErrorCode.FORBIDDEN,
            )

        # Cancel and archive
        timer.status = "cancelled"
        timer.archived_at = datetime.utcnow()
        self.database.db.commit()

        return success(data={"deleted": True, "id": str(timer_id)})
