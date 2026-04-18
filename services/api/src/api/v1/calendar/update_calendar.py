"""Update calendar endpoint — owner-only rename/describe."""

from pydantic import BaseModel
from schemas.calendar import CalendarResponse
from sqlalchemy import func
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.user import User


class UpdateCalendar(Endpoint):
    """Update a calendar's name or description (owner-only)."""

    def execute(self, calendar_id: str, params: "UpdateCalendar.Params"):
        user: User = self.user

        membership = self.database.find_by(
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

        if membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the calendar owner can update its details",
                code=ErrorCode.CALENDAR_ACCESS_DENIED,
            )

        calendar = self.database.find_by(Calendar, id=calendar_id)
        if not calendar or calendar.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        updates = {}
        if params.name is not None:
            updates["name"] = params.name
        if params.description is not None:
            updates["description"] = params.description
        if updates:
            self.database.update(calendar, **updates)

        member_count = (
            self.db.query(func.count(CalendarUser.user_id))
            .filter(
                CalendarUser.calendar_id == calendar_id,
                CalendarUser.archived_at.is_(None),
            )
            .scalar()
        ) or 1

        return success(
            data=CalendarResponse(
                id=str(calendar.id),
                name=calendar.name,
                description=calendar.description,
                is_default=calendar.is_default,
                is_shared=calendar.is_shared,
                owner_id=str(calendar.owner_id),
                user_role=membership.role,
                member_count=member_count,
                created_at=calendar.created_at,
                updated_at=calendar.updated_at,
            )
        )

    class Params(BaseModel):
        name: str | None = None
        description: str | None = None
