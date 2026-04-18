"""Create recurrence rule endpoint."""

from datetime import date, datetime, timedelta

from api.v1.calendar.dependencies import require_calendar_access
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.recipe import Recipe
from utils.models.user import User

from ._access import validate_recurrence_fields, validate_tz_name

MATERIALIZATION_WINDOW_WEEKS = 9


class CreateRecurrenceRule(Endpoint):
    """Create a new recurrence rule and materialize the first window."""

    def execute(self, params: "CreateRecurrenceRule.Params"):
        user: User = self.user

        if not params.calendar_id:
            raise APIException(
                status_code=400,
                detail="calendar_id is required",
                code=ErrorCode.RECURRENCE_RULE_CALENDAR_REQUIRED,
            )

        require_calendar_access(params.calendar_id, user, self.database)

        validate_tz_name(params.tz_name)
        validate_recurrence_fields(
            title=params.title,
            recipe_id=params.recipe_id,
            meal_type=params.meal_type,
            weekdays=params.weekdays,
            interval=params.interval,
            monthly_nth=params.monthly_nth,
            start_date=params.start_date,
            end_date=params.end_date,
            tz_name=params.tz_name,
        )

        recipe = None
        if params.recipe_id:
            recipe = self.database.find_by(Recipe, id=params.recipe_id)
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe with ID '{params.recipe_id}' not found",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )

        title = None if params.recipe_id else (params.title or "").strip() or None

        rule = MealRecurrenceRule(
            owner_id=user.id,
            calendar_id=params.calendar_id,
            title=title,
            recipe_id=params.recipe_id,
            meal_type=params.meal_type,
            weekdays=[d.lower() for d in params.weekdays],
            interval=params.interval,
            monthly_nth=params.monthly_nth,
            start_date=params.start_date,
            end_date=params.end_date,
            tz_name=params.tz_name,
            is_shared=params.is_shared,
        )
        self.database.db.add(rule)
        self.database.db.flush()

        # Materialize the initial window in the same transaction.
        from utils.recurrence.materializer import materialize

        through = date.today() + timedelta(weeks=MATERIALIZATION_WINDOW_WEEKS)
        materialize(rule, through, self.database.db)

        self.database.db.commit()
        self.database.db.refresh(rule)

        return success(
            data=_rule_to_response(rule),
            status=201,
        )

    class Params(BaseModel):
        title: str | None = None
        recipe_id: str | None = None
        # Optional at Pydantic level so missing key returns 400+265
        # instead of the generic 422. Runtime check in execute().
        calendar_id: str | None = None
        meal_type: str
        weekdays: list[str]
        interval: str
        monthly_nth: str | None = None
        start_date: date
        end_date: date | None = None
        tz_name: str
        is_shared: bool = False


class RecurrenceRuleResponse(BaseModel):
    id: str
    title: str | None = None
    recipe_id: str | None = None
    owner_id: str
    calendar_id: str
    meal_type: str
    weekdays: list[str]
    interval: str
    monthly_nth: str | None = None
    start_date: date
    end_date: date | None = None
    tz_name: str
    is_shared: bool
    materialized_through: date | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


def _rule_to_response(rule: MealRecurrenceRule) -> RecurrenceRuleResponse:
    return RecurrenceRuleResponse(
        id=str(rule.id),
        title=rule.title,
        recipe_id=str(rule.recipe_id) if rule.recipe_id else None,
        owner_id=str(rule.owner_id),
        calendar_id=str(rule.calendar_id),
        meal_type=rule.meal_type,
        weekdays=list(rule.weekdays or []),
        interval=rule.interval,
        monthly_nth=rule.monthly_nth,
        start_date=rule.start_date,
        end_date=rule.end_date,
        tz_name=rule.tz_name,
        is_shared=rule.is_shared,
        materialized_through=rule.materialized_through,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        archived_at=rule.archived_at,
    )
