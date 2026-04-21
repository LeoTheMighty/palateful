"""List meal events endpoint."""

from datetime import date, datetime, timedelta
from typing import Optional

from api.v1.calendar.dependencies import (
    get_user_calendar_ids,
    require_calendar_access,
)
from api.v1.meal_event._meal_binding import MealSummary, build_meal_summary
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from utils.api.endpoint import Endpoint, success
from utils.models.meal import Meal
from utils.models.meal_event import MealEvent
from utils.models.meal_recipe import MealRecipe
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User
from utils.recurrence.materializer import materialize


class ListMealEvents(Endpoint):
    """List meal events for the current user."""

    def execute(
        self,
        limit: int = 20,
        offset: int = 0,
        start_date: date | None = None,
        end_date: date | None = None,
        meal_type: str | None = None,
        status: str | None = None,
        calendar_id: str | None = None,
    ):
        """
        List meal events for the current user.

        Args:
            limit: Maximum number of results
            offset: Pagination offset
            start_date: Filter events on or after this date
            end_date: Filter events on or before this date
            meal_type: Filter by meal type (breakfast, lunch, dinner, snack)
            status: Filter by status

        Returns:
            Paginated list of meal events
        """
        user: User = self.user

        # Resolve the calendar scope once. When a single calendar is
        # specified, verify membership; otherwise union across every
        # calendar the user is an active member of.
        if calendar_id is not None:
            require_calendar_access(
                calendar_id, user, self.database, roles={"owner", "editor"}
            )
            scoped_calendar_ids = [calendar_id]
        else:
            scoped_calendar_ids = get_user_calendar_ids(user, self.database)

        # Ensure rule-materialized occurrences exist for the requested
        # window before the main query. Scope to the rules on the
        # calendars we're reading — matches the sharing epic's model
        # where any calendar member can see materialized occurrences for
        # that calendar's rules, not just the rule's owner.
        if end_date is not None:
            through_date = end_date + timedelta(days=1)
            try:
                active_rules = (
                    self.db.query(MealRecurrenceRule)
                    .filter(MealRecurrenceRule.calendar_id.in_(scoped_calendar_ids))
                    .filter(MealRecurrenceRule.archived_at.is_(None))
                    .all()
                )
                for rule in active_rules:
                    watermark = getattr(rule, "materialized_through", None)
                    if watermark is None or watermark < through_date:
                        materialize(rule, through_date, self.db)
            except Exception:
                # Never block a calendar read on materialization failure —
                # the nightly worker is the authoritative fallback.
                pass

        query = (
            self.db.query(MealEvent)
            .options(
                selectinload(MealEvent.meal)
                .selectinload(Meal.components)
                .selectinload(MealRecipe.recipe),
                # pbq-7: SIBLING selectinload — participants is a
                # relationship on MealEvent itself, NOT nested under
                # .meal. The response loop reads `event.participants`
                # for `participant_count`; without this option every
                # row fires a lazy-load IN query.
                selectinload(MealEvent.participants),
            )
            .filter(MealEvent.calendar_id.in_(scoped_calendar_ids))
            .filter(MealEvent.archived_at.is_(None))
        )

        # Apply date filters
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(MealEvent.scheduled_at >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(MealEvent.scheduled_at <= end_datetime)

        # Apply meal type filter
        if meal_type:
            query = query.filter(MealEvent.meal_type == meal_type)

        # Apply status filter
        if status:
            query = query.filter(MealEvent.status == status)

        # Get total count
        total = query.count()

        # Apply ordering + pagination.
        meal_events = (
            query.order_by(MealEvent.scheduled_at, MealEvent.id)
            .offset(offset)
            .limit(limit)
            .all()
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
        # Flutter's MealEvent.fromJson required owner_id on the list
        # response — omitting it here made the Flutter parser throw on
        # the 200 payload and surface as "Failed to load calendar".
        owner_id: str
        calendar_id: str
        recurrence_rule_id: str | None = None

    class Response(BaseModel):
        items: list["ListMealEvents.MealEventItem"]
        total: int
        limit: int
        offset: int
