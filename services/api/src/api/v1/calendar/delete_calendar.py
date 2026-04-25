"""Delete calendar endpoint — archive with cascade, owner-only, last-calendar guard."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.error_log import ErrorLog
from utils.models.meal_event import MealEvent
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User


class DeleteCalendar(AsyncEndpoint):
    """Archive a calendar (soft-delete) and cascade archived_at to its
    meal_events, recurrence rules, and membership rows. Owner-only.
    Forbids deleting the user's last calendar.
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

        if membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the calendar owner can delete it",
                code=ErrorCode.CALENDAR_ACCESS_DENIED,
            )

        calendar = await self.database.find_by(Calendar, id=calendar_id)
        if not calendar:
            raise APIException(  # pragma: no cover - require_calendar_access already returns 403 when calendar is missing
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        # Idempotency: already archived → 200 no-op, no duplicate audit row.
        if calendar.archived_at is not None:
            return success(data=DeleteCalendar.Response(success=True, already_archived=True))

        # Last-calendar guard — count active calendars the user owns OTHER
        # than the one being deleted. If zero remain, refuse.
        other_active_owned_count = (
            await self.db.execute(
                select(func.count(Calendar.id))
                .join(
                    CalendarUser,
                    (CalendarUser.calendar_id == Calendar.id)
                    & (CalendarUser.user_id == user.id)
                    & (CalendarUser.role == "owner")
                    & (CalendarUser.archived_at.is_(None)),
                )
                .where(
                    Calendar.archived_at.is_(None),
                    Calendar.id != calendar.id,
                )
            )
        ).scalar() or 0

        if other_active_owned_count < 1:
            raise APIException(
                status_code=400,
                detail="You can't delete your only calendar",
                code=ErrorCode.CALENDAR_CANNOT_DELETE_LAST,
            )

        now = datetime.now(UTC)
        db = self.db

        was_default = calendar.is_default

        # Cascade archive: calendar → its meal_events → its recurrence_rules →
        # membership rows. Single transaction; commit happens at request end.
        calendar.archived_at = now
        calendar.is_default = False
        db.add(calendar)

        await db.execute(
            sa_update(MealEvent)
            .where(
                MealEvent.calendar_id == calendar_id,
                MealEvent.archived_at.is_(None),
            )
            .values(archived_at=now)
        )

        await db.execute(
            sa_update(MealRecurrenceRule)
            .where(
                MealRecurrenceRule.calendar_id == calendar_id,
                MealRecurrenceRule.archived_at.is_(None),
            )
            .values(archived_at=now)
        )

        await db.execute(
            sa_update(CalendarUser)
            .where(
                CalendarUser.calendar_id == calendar_id,
                CalendarUser.archived_at.is_(None),
            )
            .values(archived_at=now)
        )

        if was_default:
            # Promote the most-recently-created remaining owned active
            # calendar to default.
            promotion_target = (
                await db.execute(
                    select(Calendar)
                    .join(
                        CalendarUser,
                        (CalendarUser.calendar_id == Calendar.id)
                        & (CalendarUser.user_id == user.id)
                        & (CalendarUser.role == "owner")
                        & (CalendarUser.archived_at.is_(None)),
                    )
                    .where(
                        Calendar.archived_at.is_(None),
                        Calendar.id != calendar.id,
                    )
                    .order_by(Calendar.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if promotion_target is not None:  # pragma: no branch — last-calendar guard above ensures another active calendar exists when was_default
                promotion_target.is_default = True
                db.add(promotion_target)

        # Audit row — service="audit" keeps it out of api-error dashboards.
        audit = ErrorLog(
            error_type="CalendarArchiveAudit",
            error_message=(
                f"Calendar {calendar.id} ('{calendar.name}') archived "
                f"by user {user.id}"
            ),
            service="audit",
            user_id=user.id,
        )
        await self.database.create(audit)

        await db.flush()

        return success(data=DeleteCalendar.Response(success=True, already_archived=False))

    class Response(BaseModel):
        success: bool
        already_archived: bool = False
