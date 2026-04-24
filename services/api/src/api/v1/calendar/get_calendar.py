"""Get calendar endpoint."""

from datetime import UTC, datetime

from schemas.calendar import CalendarDetailResponse, CalendarMemberResponse
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.user import User


class GetCalendar(AsyncEndpoint):
    """Get calendar details plus its members. 404 for non-members."""

    async def execute(self, calendar_id: str):
        user: User = self.user

        membership = await self.database.find_by(
            CalendarUser,
            user_id=user.id,
            calendar_id=calendar_id,
        )
        if not membership or membership.archived_at is not None:
            # 404 rather than 403 to avoid existence leaks.
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        calendar = await self.database.find_by(Calendar, id=calendar_id)
        if not calendar or calendar.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        # Recency tracking for switcher ordering.
        membership.last_opened_at = datetime.now(UTC)
        self.database.db.add(membership)
        await self.database.db.flush()

        # Fetch every active membership for this calendar + the corresponding user.
        all_memberships = (
            await self.db.execute(
                select(CalendarUser, User)
                .join(User, CalendarUser.user_id == User.id)
                .where(
                    CalendarUser.calendar_id == calendar_id,
                    CalendarUser.archived_at.is_(None),
                )
            )
        ).all()
        members = [
            CalendarMemberResponse(
                user_id=str(cu.user_id),
                name=u.name,
                role=cu.role,
                invited_by_id=str(cu.invited_by_id) if cu.invited_by_id else None,
                created_at=cu.created_at,
            )
            for cu, u in all_memberships
        ]

        return success(
            data=CalendarDetailResponse(
                id=str(calendar.id),
                name=calendar.name,
                description=calendar.description,
                is_default=calendar.is_default,
                is_shared=calendar.is_shared,
                owner_id=str(calendar.owner_id),
                user_role=membership.role,
                member_count=len(members),
                members=members,
                created_at=calendar.created_at,
                updated_at=calendar.updated_at,
            )
        )
