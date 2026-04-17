"""List meal events endpoint."""

from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import or_
from utils.api.endpoint import Endpoint, success
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
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

        # Ensure rule-materialized occurrences exist for the requested window
        # before the main query. Bounded work: only the user's own rules and
        # only when the rule's watermark is behind the request.
        if end_date is not None:
            through_date = end_date + timedelta(days=1)
            try:
                active_rules = (
                    self.db.query(MealRecurrenceRule)
                    .filter(MealRecurrenceRule.owner_id == user.id)
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

        # Build query - include events user owns OR is a participant of
        query = (
            self.db.query(MealEvent)
            .outerjoin(
                MealEventParticipant,
                MealEvent.id == MealEventParticipant.meal_event_id,
            )
            .filter(
                or_(
                    MealEvent.owner_id == user.id,
                    MealEventParticipant.user_id == user.id,
                )
            )
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

        # Get distinct results (avoid duplicates from join)
        query = query.distinct(MealEvent.id)

        # Get total count
        total = query.count()

        # Apply ordering and pagination
        # PostgreSQL DISTINCT ON requires the ORDER BY to start with the
        # DISTINCT ON column, so include MealEvent.id first.
        meal_events = (
            query.order_by(MealEvent.id, MealEvent.scheduled_at).offset(offset).limit(limit).all()
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
                    participant_count=len(event.participants),
                    created_at=event.created_at,
                    owner_id=str(event.owner_id),
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
        participant_count: int = 0
        created_at: datetime
        # Flutter's MealEvent.fromJson required owner_id on the list
        # response — omitting it here made the Flutter parser throw on
        # the 200 payload and surface as "Failed to load calendar".
        owner_id: str
        recurrence_rule_id: str | None = None

    class Response(BaseModel):
        items: list["ListMealEvents.MealEventItem"]
        total: int
        limit: int
        offset: int
