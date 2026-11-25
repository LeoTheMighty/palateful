"""Delete recurrence rule endpoint (scoped)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from api.v1.calendar.dependencies import require_calendar_access_async
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User


class DeleteRecurrenceRule(AsyncEndpoint):
    """Delete or split a recurrence rule.

    scope=series (default): archive the rule, drop all future materialized rows.
    scope=this_and_following: set end_date = occurrence_date - 1 day, drop
                              materialized rows >= occurrence_date.
    scope=this_occurrence: tombstone the single matching meal_event row —
                           set archived_at but keep recurrence_rule_id, so
                           the materializer treats the slot as occupied and
                           doesn't resurrect it.
    """

    async def execute(
        self,
        rule_id: str,
        scope: str = "series",
        occurrence_date: date | None = None,
    ):
        user: User = self.user

        rule = await self.database.find_by(MealRecurrenceRule, id=rule_id)
        if rule is None:
            # Also fetch archived rules so repeat-delete stays idempotent.
            rule = (
                await self.db.execute(
                    select(MealRecurrenceRule)
                    .where(MealRecurrenceRule.id == rule_id)
                    .limit(1)
                )
            ).scalars().first()
        if not rule:
            raise APIException(
                status_code=404,
                detail=f"Recurrence rule with ID '{rule_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )
        # Calendar membership is the sole edit gate. Mask 403 → 404 so
        # non-members can't enumerate rule ids (matches the existence-leak
        # policy used on get_recurrence_rule / delete_meal_event).
        try:
            await require_calendar_access_async(
                str(rule.calendar_id), user, self.database
            )
        except APIException as exc:
            if exc.status_code == 403:
                raise APIException(
                    status_code=404,
                    detail=f"Recurrence rule with ID '{rule_id}' not found",
                    code=ErrorCode.NOT_FOUND,
                ) from exc
            raise  # pragma: no cover — require_calendar_access only raises 403

        if scope == "series":
            return await self._delete_series(rule)
        if scope == "this_and_following":
            if occurrence_date is None:
                raise APIException(
                    status_code=400,
                    detail="occurrence_date is required for this_and_following scope",
                    code=ErrorCode.VALIDATION_ERROR,
                )
            return await self._split_end(rule, occurrence_date)
        if scope == "this_occurrence":
            if occurrence_date is None:
                raise APIException(
                    status_code=400,
                    detail="occurrence_date is required for this_occurrence scope",
                    code=ErrorCode.VALIDATION_ERROR,
                )
            return await self._delete_single_occurrence(rule, occurrence_date)

        raise APIException(
            status_code=400,
            detail=f"Invalid scope: '{scope}'",
            code=ErrorCode.VALIDATION_ERROR,
        )

    async def _delete_series(self, rule: MealRecurrenceRule):
        if rule.archived_at is not None:
            # Idempotent: re-delete is a no-op.
            return success(data={"deleted": True, "id": str(rule.id)})

        rule.archived_at = datetime.utcnow()

        tz = ZoneInfo(rule.tz_name)
        today_utc_cutoff = datetime.combine(
            date.today(), time.min, tzinfo=tz
        )

        await self.db.execute(
            sa_delete(MealEvent)
            .where(
                MealEvent.recurrence_rule_id == rule.id,
                MealEvent.scheduled_at >= today_utc_cutoff,
            )
        )

        await self.db.commit()
        return success(data={"deleted": True, "id": str(rule.id)})

    async def _split_end(self, rule: MealRecurrenceRule, occurrence_date: date):
        new_end = occurrence_date - timedelta(days=1)
        if rule.end_date is not None and rule.end_date < new_end:
            # Already ended before the cut — idempotent no-op.
            await self.db.commit()
            return success(data={"id": str(rule.id), "end_date": rule.end_date.isoformat()})

        rule.end_date = new_end

        tz = ZoneInfo(rule.tz_name)
        cutoff_utc = datetime.combine(occurrence_date, time.min, tzinfo=tz)
        await self.db.execute(
            sa_delete(MealEvent)
            .where(
                MealEvent.recurrence_rule_id == rule.id,
                MealEvent.scheduled_at >= cutoff_utc,
            )
        )

        await self.db.commit()
        return success(data={"id": str(rule.id), "end_date": new_end.isoformat()})

    async def _delete_single_occurrence(
        self, rule: MealRecurrenceRule, occurrence_date: date
    ):
        tz = ZoneInfo(rule.tz_name)
        start_utc = datetime.combine(occurrence_date, time.min, tzinfo=tz)
        end_utc = datetime.combine(
            occurrence_date + timedelta(days=1), time.min, tzinfo=tz
        )

        event = (
            await self.db.execute(
                select(MealEvent)
                .where(MealEvent.recurrence_rule_id == rule.id)
                .where(MealEvent.scheduled_at >= start_utc)
                .where(MealEvent.scheduled_at < end_utc)
                .where(MealEvent.archived_at.is_(None))
                .limit(1)
            )
        ).scalars().first()
        if event is not None:
            # Tombstone, don't detach. The row keeps `recurrence_rule_id` so
            # the materializer still sees it occupying this slot and skips
            # re-inserting it on the next window advance. Detaching (setting
            # `recurrence_rule_id = NULL`) made the row invisible to
            # `materialize()`'s dedup query, which resurrected the occurrence.
            # `archived_at` alone hides it from clients — list_meal_events and
            # every other read path already filter `archived_at IS NULL`.
            event.archived_at = datetime.utcnow()

        await self.db.commit()
        return success(data={"deleted": True, "id": str(rule.id)})
