"""Remove a calendar member — owner-only, archive-only (preserves last_opened_at)."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.activity import Activity
from utils.models.calendar_user import CalendarUser
from utils.models.error_log import ErrorLog
from utils.models.user import User


class RemoveCalendarMember(AsyncEndpoint):
    """DELETE /calendars/{id}/members/{user_id}.

    Owner-only. Archives the target's `calendar_users` row. Owner
    cannot remove themselves — must transfer ownership first; same
    error code as leave-while-owner (`CALENDAR_OWNER_CANNOT_LEAVE`).
    `meal_event_participants` rows are NOT cleaned up — they're an
    orthogonal primitive (per cal-share principle #7).
    """

    async def execute(self, calendar_id: str, target_user_id: str):
        user: User = self.user

        caller_row = await self.database.find_by(
            CalendarUser,
            user_id=user.id,
            calendar_id=calendar_id,
        )
        if not caller_row or caller_row.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )
        if caller_row.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the calendar owner can remove members",
                code=ErrorCode.CALENDAR_ACCESS_DENIED,
            )

        # Owner removing themselves → forbidden via the same code as leave.
        if str(target_user_id) == str(user.id):
            raise APIException(
                status_code=409,
                detail=(
                    "The owner can't remove themselves — transfer ownership "
                    "first or delete the calendar"
                ),
                code=ErrorCode.CALENDAR_OWNER_CANNOT_LEAVE,
            )

        target_row = await self.database.find_by(
            CalendarUser,
            user_id=target_user_id,
            calendar_id=calendar_id,
        )
        if not target_row or target_row.archived_at is not None:
            raise APIException(
                status_code=404,
                detail="Member not found on this calendar",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        now = datetime.now(UTC)
        target_row.archived_at = now
        self.db.add(target_row)

        self.db.add(Activity(
            user_id=user.id,
            action="removed",
            resource_type="calendar",
            resource_id=calendar_id,
            target_type="user",
            target_id=target_user_id,
            details={"removed_by_id": str(user.id)},
        ))

        await self.database.create(ErrorLog(
            error_type="CalendarMemberAudit",
            error_message=(
                f"User {target_user_id} removed from calendar "
                f"{calendar_id} by user {user.id}"
            ),
            service="audit",
            user_id=user.id,
        ))

        await self.db.flush()

        return success(data=RemoveCalendarMember.Response(success=True))

    class Response(BaseModel):
        success: bool
