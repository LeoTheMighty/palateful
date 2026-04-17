"""Get recurrence rule endpoint."""

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.user import User

from ._access import user_can_read_rule
from .create_recurrence_rule import _rule_to_response


class GetRecurrenceRule(Endpoint):
    """Return a single rule if the user can see it."""

    def execute(self, rule_id: str):
        user: User = self.user

        rule = self.database.find_by(MealRecurrenceRule, id=rule_id)
        if not rule or rule.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Recurrence rule with ID '{rule_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )
        if not user_can_read_rule(self.database, rule, user):
            raise APIException(
                status_code=404,
                detail=f"Recurrence rule with ID '{rule_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )

        return success(data=_rule_to_response(rule))
