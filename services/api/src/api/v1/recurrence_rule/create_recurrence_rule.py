"""Create recurrence rule endpoint."""

from datetime import date, datetime, timedelta

from api.v1.calendar.dependencies import require_calendar_access_async
from api.v1.meal_event._meal_binding import (
    MealSummary,
    build_meal_summary,
    require_meal_available_async,
    validate_recipe_meal_xor,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.recipe import Recipe
from utils.models.user import User

from ._access import validate_recurrence_fields, validate_tz_name

MATERIALIZATION_WINDOW_WEEKS = 9


def _materialize_sync(rule_id: str, through_date: date) -> None:
    """Threadpool-side wrapper: open a fresh sync Session, load rule,
    call sync `materialize`, commit, close.

    Mirrors `api.v1.meal_event.list_meal_events._materialize_sync`. No-op
    if `SessionLocal` isn't configured (test env with `DATABASE_URL=""`).
    """
    from utils.recurrence.materializer import materialize
    from utils.services.database import SessionLocal

    if SessionLocal is None:
        return
    session = SessionLocal()
    try:
        rule = (
            session.query(MealRecurrenceRule)
            .filter(MealRecurrenceRule.id == rule_id)
            .first()
        )
        if rule is None:
            return
        materialize(rule, through_date, session)
        session.commit()
    finally:
        session.close()


async def _run_materialize(rule_id: str, through_date: date) -> None:
    """Async entrypoint that dispatches the sync materializer onto the
    threadpool (the materializer uses a sync Session).
    """
    await run_in_threadpool(_materialize_sync, rule_id, through_date)


class CreateRecurrenceRule(AsyncEndpoint):
    """Create a new recurrence rule and materialize the first window."""

    async def execute(self, params: "CreateRecurrenceRule.Params"):
        user: User = self.user

        if not params.calendar_id:
            raise APIException(
                status_code=400,
                detail="calendar_id is required",
                code=ErrorCode.RECURRENCE_RULE_CALENDAR_REQUIRED,
            )

        await require_calendar_access_async(
            params.calendar_id, user, self.database
        )

        validate_recipe_meal_xor(params.recipe_id, params.meal_id)

        validate_tz_name(params.tz_name)
        validate_recurrence_fields(
            title=params.title,
            recipe_id=params.recipe_id,
            meal_id=params.meal_id,
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
            recipe = await self.database.find_by(Recipe, id=params.recipe_id)
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe with ID '{params.recipe_id}' not found",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )

        meal = None
        if params.meal_id:
            meal = await require_meal_available_async(
                self.db, params.meal_id, user
            )

        # When recipe_id or meal_id is set, title is derived at read time
        # from the linked entity's name (materializer `_resolve_title`).
        # Only free-text rules store their own title.
        title = (
            None
            if (params.recipe_id or params.meal_id)
            else (params.title or "").strip() or None
        )

        rule = MealRecurrenceRule(
            owner_id=user.id,
            calendar_id=params.calendar_id,
            title=title,
            recipe_id=params.recipe_id,
            meal_id=params.meal_id,
            meal_type=params.meal_type,
            weekdays=[d.lower() for d in params.weekdays],
            interval=params.interval,
            monthly_nth=params.monthly_nth,
            start_date=params.start_date,
            end_date=params.end_date,
            tz_name=params.tz_name,
            is_shared=params.is_shared,
        )
        self.db.add(rule)
        await self.db.flush()

        # Commit first so a fresh sync session inside the threadpool
        # materializer can see the new rule. Trade-off: if materialize
        # fails below, the rule is durable without its initial window —
        # the nightly worker is the authoritative fallback.
        await self.db.commit()

        through = date.today() + timedelta(weeks=MATERIALIZATION_WINDOW_WEEKS)
        await _run_materialize(str(rule.id), through)

        await self.db.refresh(rule)

        return success(
            data=_rule_to_response(rule, meal=meal),
            status=201,
        )

    class Params(BaseModel):
        title: str | None = None
        recipe_id: str | None = None
        meal_id: str | None = None
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
    meal_id: str | None = None
    meal_summary: MealSummary | None = None
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


def _rule_to_response(
    rule: MealRecurrenceRule, *, meal=None
) -> RecurrenceRuleResponse:
    meal_summary = build_meal_summary(meal) if meal is not None else None
    return RecurrenceRuleResponse(
        id=str(rule.id),
        title=rule.title,
        recipe_id=str(rule.recipe_id) if rule.recipe_id else None,
        meal_id=str(rule.meal_id) if rule.meal_id else None,
        meal_summary=meal_summary,
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
