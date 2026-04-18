"""Delete calendar endpoint — archive with cascade, owner-only, last-calendar guard."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.error_log import ErrorLog
from utils.models.meal_event import MealEvent
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User


class DeleteCalendar(Endpoint):
    """Archive a calendar (soft-delete) and cascade archived_at to its
    meal_events, recurrence rules, and membership rows. Owner-only.
    Forbids deleting the user's last calendar.
    """

    def execute(self, calendar_id: str):
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
                detail="Only the calendar owner can delete it",
                code=ErrorCode.CALENDAR_ACCESS_DENIED,
            )

        calendar = self.database.find_by(Calendar, id=calendar_id)
        if not calendar:
            raise APIException(
                status_code=404,
                detail=f"Calendar with ID '{calendar_id}' not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )

        # Idempotency: already archived → 200 no-op, no duplicate audit row.
        if calendar.archived_at is not None:
            return success(data=DeleteCalendar.Response(success=True, already_archived=True))

        # Last-calendar guard — count active calendars the user owns OTHER
        # than the one being deleted. If zero remain, refuse. Counting
        # "other than target" instead of "<= 1 total" makes the intent
        # explicit and avoids an off-by-one if a concurrent archive
        # lands between the count and the update.
        other_active_owned_count = (
            self.db.query(func.count(Calendar.id))
            .join(
                CalendarUser,
                (CalendarUser.calendar_id == Calendar.id)
                & (CalendarUser.user_id == user.id)
                & (CalendarUser.role == "owner")
                & (CalendarUser.archived_at.is_(None)),
            )
            .filter(
                Calendar.archived_at.is_(None),
                Calendar.id != calendar.id,
            )
            .scalar()
        ) or 0

        if other_active_owned_count < 1:
            raise APIException(
                status_code=400,
                detail="You can't delete your only calendar",
                code=ErrorCode.CALENDAR_CANNOT_DELETE_LAST,
            )

        now = datetime.now(UTC)
        db = self.db

        # If deleting the user's default, promote another owned active
        # calendar to default so the user still has exactly one active
        # default afterwards. Archive flips archived_at first, so the
        # partial unique index does NOT see two active defaults during
        # the transition.
        was_default = calendar.is_default

        # Cascade archive: calendar → its meal_events → its recurrence_rules →
        # membership rows. Single transaction; commit happens at request end.
        calendar.archived_at = now
        calendar.is_default = False
        db.add(calendar)

        db.query(MealEvent).filter(
            MealEvent.calendar_id == calendar_id,
            MealEvent.archived_at.is_(None),
        ).update({MealEvent.archived_at: now}, synchronize_session=False)

        db.query(MealRecurrenceRule).filter(
            MealRecurrenceRule.calendar_id == calendar_id,
            MealRecurrenceRule.archived_at.is_(None),
        ).update({MealRecurrenceRule.archived_at: now}, synchronize_session=False)

        db.query(CalendarUser).filter(
            CalendarUser.calendar_id == calendar_id,
            CalendarUser.archived_at.is_(None),
        ).update({CalendarUser.archived_at: now}, synchronize_session=False)

        if was_default:
            # Promote the most-recently-created remaining owned active
            # calendar to default. Matches the Flutter fallback policy
            # in cal-found-4 AC #6, and keeps the
            # `_ensure_default_calendar` hook from re-seeding a second
            # "My Calendar" on the user's next request.
            promotion_target = (
                self.db.query(Calendar)
                .join(
                    CalendarUser,
                    (CalendarUser.calendar_id == Calendar.id)
                    & (CalendarUser.user_id == user.id)
                    & (CalendarUser.role == "owner")
                    & (CalendarUser.archived_at.is_(None)),
                )
                .filter(
                    Calendar.archived_at.is_(None),
                    Calendar.id != calendar.id,
                )
                .order_by(Calendar.created_at.desc())
                .first()
            )
            if promotion_target is not None:  # pragma: no branch — last-calendar guard above ensures another active calendar exists when was_default
                promotion_target.is_default = True
                db.add(promotion_target)

        # Audit row — service="audit" keeps it out of api-error dashboards
        # (which filter service="api"). Matches promote_admin.py precedent.
        audit = ErrorLog(
            error_type="CalendarArchiveAudit",
            error_message=(
                f"Calendar {calendar.id} ('{calendar.name}') archived "
                f"by user {user.id}"
            ),
            service="audit",
            user_id=user.id,
        )
        self.database.create(audit)

        db.flush()

        return success(data=DeleteCalendar.Response(success=True, already_archived=False))

    class Response(BaseModel):
        success: bool
        already_archived: bool = False
