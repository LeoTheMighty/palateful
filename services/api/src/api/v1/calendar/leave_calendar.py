"""Leave a calendar — caller's own row archived. Owner cannot leave."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.activity import Activity
from utils.models.calendar_user import CalendarUser
from utils.models.error_log import ErrorLog
from utils.models.user import User


class LeaveCalendar(AsyncEndpoint):
    """POST /calendars/{id}/leave.

    Archives the caller's own `calendar_users` row. Owners cannot
    leave — they must transfer ownership first or delete the calendar.
    Same error code as remove-self-as-owner: `CALENDAR_OWNER_CANNOT_LEAVE`.
    """

    async def execute(self, calendar_id: str):
        user: User = self.user

        membership = await self.database.find_by(
            CalendarUser,
            user_id=user.id,
            calendar_id=calendar_id,
        )
        if not membership or membership.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )
        if membership.role == "owner":
            raise APIException(
                status_code=409,
                detail=(
                    "Owners can't leave — transfer ownership first or "
                    "delete the calendar"
                ),
                code=ErrorCode.CALENDAR_OWNER_CANNOT_LEAVE,
            )

        membership.archived_at = datetime.now(UTC)
        self.db.add(membership)

        self.db.add(Activity(
            user_id=user.id,
            action="left",
            resource_type="calendar",
            resource_id=calendar_id,
            target_type="user",
            target_id=user.id,
            details={},
        ))

        await self.database.create(ErrorLog(
            error_type="CalendarMemberAudit",
            error_message=(
                f"User {user.id} left calendar {calendar_id}"
            ),
            service="audit",
            user_id=user.id,
        ))

        await self.db.flush()

        return success(data=LeaveCalendar.Response(success=True))

    class Response(BaseModel):
        success: bool
