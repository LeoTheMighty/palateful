"""List meal events endpoint."""

from datetime import date, datetime, timedelta
from typing import Optional

from api.v1.calendar.dependencies import (
    get_user_calendar_ids_async,
    require_calendar_access_async,
)
from api.v1.meal_event._meal_binding import MealSummary, build_meal_summary
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.meal import Meal
from utils.models.meal_event import MealEvent
from utils.models.meal_recipe import MealRecipe
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User


def _materialize_sync(rule_id: str, through_date: date) -> None:
    """Threadpool-side wrapper: build a fresh sync Session, load rule,
    call sync `materialize`, commit, close.

    No-op if `SessionLocal` isn't configured (test env with
    `DATABASE_URL=""` — the rule-materialization path is async-loop-
    irrelevant there anyway).
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


class ListMealEvents(AsyncEndpoint):
    """List meal events for the current user."""

    async def execute(
        self,
        limit: int = 20,
        offset: int = 0,
        start_date: date | None = None,
        end_date: date | None = None,
        meal_type: str | None = None,
        status: str | None = None,
        calendar_id: str | None = None,
    ):
        """List meal events for the current user."""
        user: User = self.user

        # Resolve the calendar scope once. When a single calendar is
        # specified, verify membership; otherwise union across every
        # calendar the user is an active member of.
        if calendar_id is not None:
            await require_calendar_access_async(
                calendar_id, user, self.database, roles={"owner", "editor"}
            )
            scoped_calendar_ids = [calendar_id]
        else:
            scoped_calendar_ids = await get_user_calendar_ids_async(
                user, self.database
            )

        # Ensure rule-materialized occurrences exist for the requested
        # window before the main query. Materialize dispatches to the
        # threadpool because the materializer takes a sync Session.
        if end_date is not None:
            through_date = end_date + timedelta(days=1)
            try:
                rules_result = await self.db.execute(
                    select(MealRecurrenceRule)
                    .where(MealRecurrenceRule.calendar_id.in_(scoped_calendar_ids))
                    .where(MealRecurrenceRule.archived_at.is_(None))
                )
                active_rules = list(rules_result.scalars().all())
                for rule in active_rules:
                    watermark = getattr(rule, "materialized_through", None)
                    if watermark is None or watermark < through_date:
                        await _run_materialize(str(rule.id), through_date)
            except Exception:
                # Never block a calendar read on materialization failure —
                # the nightly worker is the authoritative fallback.
                pass

        stmt = (
            select(MealEvent)
            .options(
                selectinload(MealEvent.meal)
                .selectinload(Meal.components)
                .selectinload(MealRecipe.recipe),
                # pbq-7: SIBLING selectinload — participants is a
                # relationship on MealEvent itself, NOT nested under
                # .meal. Without this, participant_count lazy-loads.
                selectinload(MealEvent.participants),
                selectinload(MealEvent.recipe),
            )
            .where(MealEvent.calendar_id.in_(scoped_calendar_ids))
            .where(MealEvent.archived_at.is_(None))
        )

        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            stmt = stmt.where(MealEvent.scheduled_at >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            stmt = stmt.where(MealEvent.scheduled_at <= end_datetime)

        if meal_type:
            stmt = stmt.where(MealEvent.meal_type == meal_type)

        if status:
            stmt = stmt.where(MealEvent.status == status)

        # Total count — mirror sync `.count()` by wrapping in subquery.
        # Use `.scalar()` (not `.scalar_one()`) so mock fixtures that
        # supply empty results fall back to 0 cleanly. Coerce non-int
        # scalars (mock fixtures can reuse the same result for multiple
        # execute() calls) to 0 defensively.
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_val = (await self.db.execute(count_stmt)).scalar()
        total = int(count_val) if isinstance(count_val, int) else 0

        paged_stmt = (
            stmt.order_by(MealEvent.scheduled_at, MealEvent.id)
            .offset(offset)
            .limit(limit)
        )
        meal_events = list(
            (await self.db.execute(paged_stmt)).scalars().all()
        )

        items = []
        for event in meal_events:
            recipe_summary = None
            if event.recipe:
                recipe_summary = ListMealEvents.RecipeSummary(
                    id=str(event.recipe.id),
                    name=event.recipe.name,
                    description=event.recipe.description,
                    prep_time=event.recipe.prep_time,
                    cook_time=event.recipe.cook_time,
                    image_url=event.recipe.image_url,
                )

            meal_summary = build_meal_summary(event.meal) if event.meal else None

            items.append(
                ListMealEvents.MealEventItem(
                    id=str(event.id),
                    title=event.title,
                    description=event.description,
                    scheduled_at=event.scheduled_at,
                    meal_type=event.meal_type,
                    status=event.status,
                    is_shared=event.is_shared,
                    is_recurring=event.is_recurring,
                    recipe=recipe_summary,
                    meal_id=str(event.meal_id) if event.meal_id else None,
                    meal_summary=meal_summary,
                    participant_count=len(event.participants),
                    created_at=event.created_at,
                    owner_id=str(event.owner_id),
                    calendar_id=str(event.calendar_id),
                    recurrence_rule_id=(
                        str(event.recurrence_rule_id)
                        if event.recurrence_rule_id
                        else None
                    ),
                )
            )

        return success(
            data=ListMealEvents.Response(
                items=items, total=total, limit=limit, offset=offset
            )
        )

    class RecipeSummary(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        image_url: str | None = None

    class MealEventItem(BaseModel):
        id: str
        title: str
        description: str | None = None
        scheduled_at: datetime
        meal_type: str
        status: str
        is_shared: bool
        is_recurring: bool
        recipe: Optional["ListMealEvents.RecipeSummary"] = None
        meal_id: str | None = None
        meal_summary: MealSummary | None = None
        participant_count: int = 0
        created_at: datetime
        owner_id: str
        calendar_id: str
        recurrence_rule_id: str | None = None

    class Response(BaseModel):
        items: list["ListMealEvents.MealEventItem"]
        total: int
        limit: int
        offset: int
