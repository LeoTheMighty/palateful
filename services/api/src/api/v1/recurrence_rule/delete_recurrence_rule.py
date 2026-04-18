"""Delete recurrence rule endpoint (scoped)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from api.v1.calendar.dependencies import require_calendar_access
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User


class DeleteRecurrenceRule(Endpoint):
    """Delete or split a recurrence rule.

    scope=series (default): archive the rule, drop all future materialized rows.
    scope=this_and_following: set end_date = occurrence_date - 1 day, drop
                              materialized rows >= occurrence_date.
    scope=this_occurrence: soft-delete the single matching meal_event row
                           (detach-on-edit semantics).
    """

    def execute(
        self,
        rule_id: str,
        scope: str = "series",
        occurrence_date: date | None = None,
    ):
        user: User = self.user

        rule = self.database.find_by(MealRecurrenceRule, id=rule_id)
        if rule is None:
            # Also fetch archived rules so repeat-delete stays idempotent.
            rule = (
                self.database.db.query(MealRecurrenceRule)
                .filter(MealRecurrenceRule.id == rule_id)
                .first()
            )
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
            require_calendar_access(str(rule.calendar_id), user, self.database)
        except APIException as exc:
            if exc.status_code == 403:
                raise APIException(
                    status_code=404,
                    detail=f"Recurrence rule with ID '{rule_id}' not found",
                    code=ErrorCode.NOT_FOUND,
                ) from exc
            raise

        if scope == "series":
            return self._delete_series(rule)
        if scope == "this_and_following":
            if occurrence_date is None:
                raise APIException(
                    status_code=400,
                    detail="occurrence_date is required for this_and_following scope",
                    code=ErrorCode.VALIDATION_ERROR,
                )
            return self._split_end(rule, occurrence_date)
        if scope == "this_occurrence":
            if occurrence_date is None:
                raise APIException(
                    status_code=400,
                    detail="occurrence_date is required for this_occurrence scope",
                    code=ErrorCode.VALIDATION_ERROR,
                )
            return self._delete_single_occurrence(rule, occurrence_date)

        raise APIException(
            status_code=400,
            detail=f"Invalid scope: '{scope}'",
            code=ErrorCode.VALIDATION_ERROR,
        )

    def _delete_series(self, rule: MealRecurrenceRule):
        if rule.archived_at is not None:
            # Idempotent: re-delete is a no-op.
            return success(data={"deleted": True, "id": str(rule.id)})

        rule.archived_at = datetime.utcnow()

        tz = ZoneInfo(rule.tz_name)
        today_utc_cutoff = datetime.combine(
            date.today(), time.min, tzinfo=tz
        )

        self.database.db.query(MealEvent).filter(
            MealEvent.recurrence_rule_id == rule.id,
            MealEvent.scheduled_at >= today_utc_cutoff,
        ).delete(synchronize_session=False)

        self.database.db.commit()
        return success(data={"deleted": True, "id": str(rule.id)})

    def _split_end(self, rule: MealRecurrenceRule, occurrence_date: date):
        new_end = occurrence_date - timedelta(days=1)
        if rule.end_date is not None and rule.end_date < new_end:
            # Already ended before the cut — idempotent no-op.
            self.database.db.commit()
            return success(data={"id": str(rule.id), "end_date": rule.end_date.isoformat()})

        rule.end_date = new_end

        tz = ZoneInfo(rule.tz_name)
        cutoff_utc = datetime.combine(occurrence_date, time.min, tzinfo=tz)
        self.database.db.query(MealEvent).filter(
            MealEvent.recurrence_rule_id == rule.id,
            MealEvent.scheduled_at >= cutoff_utc,
        ).delete(synchronize_session=False)

        self.database.db.commit()
        return success(data={"id": str(rule.id), "end_date": new_end.isoformat()})

    def _delete_single_occurrence(
        self, rule: MealRecurrenceRule, occurrence_date: date
    ):
        tz = ZoneInfo(rule.tz_name)
        start_utc = datetime.combine(occurrence_date, time.min, tzinfo=tz)
        end_utc = datetime.combine(
            occurrence_date + timedelta(days=1), time.min, tzinfo=tz
        )

        event = (
            self.database.db.query(MealEvent)
            .filter(MealEvent.recurrence_rule_id == rule.id)
            .filter(MealEvent.scheduled_at >= start_utc)
            .filter(MealEvent.scheduled_at < end_utc)
            .filter(MealEvent.archived_at.is_(None))
            .first()
        )
        if event is not None:
            event.archived_at = datetime.utcnow()
            # Detach so a subsequent materialize pass doesn't re-insert.
            event.recurrence_rule_id = None

        self.database.db.commit()
        return success(data={"deleted": True, "id": str(rule.id)})
