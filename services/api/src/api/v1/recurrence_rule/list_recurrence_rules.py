"""List recurrence rules endpoint."""

from api.v1.calendar.dependencies import (
    get_user_calendar_ids_async,
    require_calendar_access_async,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User

from .create_recurrence_rule import RecurrenceRuleResponse, _rule_to_response


class ListRecurrenceRules(AsyncEndpoint):
    """List active rules the user can access via calendar membership."""

    async def execute(self, calendar_id: str | None = None):
        user: User = self.user

        if calendar_id is not None:
            await require_calendar_access_async(
                calendar_id, user, self.database
            )
            scoped_calendar_ids = [calendar_id]
        else:
            scoped_calendar_ids = await get_user_calendar_ids_async(
                user, self.database
            )

        rules_result = await self.db.execute(
            select(MealRecurrenceRule)
            .where(MealRecurrenceRule.archived_at.is_(None))
            .where(MealRecurrenceRule.calendar_id.in_(scoped_calendar_ids))
            .order_by(MealRecurrenceRule.created_at.desc())
        )
        rules = list(rules_result.scalars().all())

        # Batch-fetch Meals referenced by Meal-linked rules so the
        # meal_summary hydration stays O(1) queries regardless of list
        # size. Rules without meal_id never touch this branch.
        meal_ids = {rule.meal_id for rule in rules if rule.meal_id is not None}
        meals_by_id = {}
        if meal_ids:
            meal_rows_result = await self.db.execute(
                select(Meal)
                .options(
                    selectinload(Meal.components).selectinload(MealRecipe.recipe)
                )
                .where(Meal.id.in_(meal_ids))
            )
            meals_by_id = {
                meal.id: meal for meal in meal_rows_result.scalars().all()
            }

        return success(
            data=ListRecurrenceRules.Response(
                items=[
                    _rule_to_response(
                        r, meal=meals_by_id.get(r.meal_id) if r.meal_id else None
                    )
                    for r in rules
                ],
                total=len(rules),
            )
        )

    class Response(BaseModel):
        items: list[RecurrenceRuleResponse]
        total: int
