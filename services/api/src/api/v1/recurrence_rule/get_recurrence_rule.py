"""Get recurrence rule endpoint."""

from api.v1.calendar.dependencies import require_calendar_access
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User

from .create_recurrence_rule import _rule_to_response


class GetRecurrenceRule(Endpoint):
    """Return a single rule if the user can see it via calendar membership."""

    def execute(self, rule_id: str):
        user: User = self.user

        rule = self.database.find_by(MealRecurrenceRule, id=rule_id)
        if not rule or rule.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Recurrence rule with ID '{rule_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )

        # Mask non-members as 404 — no existence leak for reads.
        try:
            require_calendar_access(str(rule.calendar_id), user, self.database)
        except APIException as exc:
            if exc.status_code == 403:
                raise APIException(
                    status_code=404,
                    detail=f"Recurrence rule with ID '{rule_id}' not found",
                    code=ErrorCode.NOT_FOUND,
                ) from exc
            raise  # pragma: no cover — require_calendar_access only raises 403

        meal = None
        if rule.meal_id is not None:
            meal = (
                self.database.db.query(Meal)
                .options(
                    selectinload(Meal.components).selectinload(MealRecipe.recipe)
                )
                .filter(Meal.id == rule.meal_id)
                .first()
            )
        return success(data=_rule_to_response(rule, meal=meal))
