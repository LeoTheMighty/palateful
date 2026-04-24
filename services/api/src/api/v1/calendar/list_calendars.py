"""List calendars endpoint."""

from schemas.calendar import CalendarListResponse, CalendarResponse
from sqlalchemy import func, select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.user import User


class ListCalendars(AsyncEndpoint):
    """List every calendar the authenticated user is an active member of."""

    async def execute(self):
        user: User = self.user

        # pbq-6: scope the member-count aggregate to the user's calendar
        # set. The old subquery aggregated the entire `calendar_users`
        # table (hash-aggregate over every row in the DB); scoping to
        # ``calendar_id IN (the user's calendars)`` lets Postgres hit
        # the `ix_calendar_users_calendar_id` index and aggregate a
        # small per-request slice instead.
        user_calendar_rows = (
            await self.db.execute(
                select(CalendarUser.calendar_id).where(
                    CalendarUser.user_id == user.id,
                    CalendarUser.archived_at.is_(None),
                )
            )
        ).all()
        user_calendar_ids = [row[0] for row in user_calendar_rows]

        member_count_subq = (
            select(
                CalendarUser.calendar_id,
                func.count(CalendarUser.user_id).label("member_count"),
            )
            .where(
                CalendarUser.archived_at.is_(None),
                CalendarUser.calendar_id.in_(user_calendar_ids),
            )
            .group_by(CalendarUser.calendar_id)
            .subquery()
        )

        rows = (
            await self.db.execute(
                select(
                    Calendar,
                    CalendarUser.role.label("user_role"),
                    func.coalesce(member_count_subq.c.member_count, 1).label(
                        "member_count"
                    ),
                )
                .join(
                    CalendarUser,
                    (Calendar.id == CalendarUser.calendar_id)
                    & (CalendarUser.user_id == user.id)
                    & (CalendarUser.archived_at.is_(None)),
                )
                .outerjoin(
                    member_count_subq,
                    Calendar.id == member_count_subq.c.calendar_id,
                )
                .where(Calendar.archived_at.is_(None))
                .order_by(Calendar.is_default.desc(), Calendar.created_at.desc())
            )
        ).all()

        items = [
            CalendarResponse(
                id=str(cal.id),
                name=cal.name,
                description=cal.description,
                is_default=cal.is_default,
                is_shared=cal.is_shared,
                owner_id=str(cal.owner_id),
                user_role=user_role,
                member_count=member_count,
                created_at=cal.created_at,
                updated_at=cal.updated_at,
            )
            for cal, user_role, member_count in rows
        ]

        return success(data=CalendarListResponse(items=items))
