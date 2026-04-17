"""List recurrence rules endpoint."""

from pydantic import BaseModel
from sqlalchemy import or_
from utils.api.endpoint import Endpoint, success
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.pantry_user import PantryUser
from utils.models.user import User

from .create_recurrence_rule import RecurrenceRuleResponse, _rule_to_response


class ListRecurrenceRules(Endpoint):
    """List active rules visible to the current user."""

    def execute(self):
        user: User = self.user

        my_pantry_ids = [
            row.pantry_id
            for row in self.database.db.query(PantryUser)
            .filter(PantryUser.user_id == user.id)
            .all()
        ]
        if my_pantry_ids:
            pantry_mate_ids = [
                row.user_id
                for row in self.database.db.query(PantryUser)
                .filter(PantryUser.pantry_id.in_(my_pantry_ids))
                .filter(PantryUser.user_id != user.id)
                .all()
            ]
        else:
            pantry_mate_ids = []

        query = (
            self.database.db.query(MealRecurrenceRule)
            .filter(MealRecurrenceRule.archived_at.is_(None))
        )
        if pantry_mate_ids:
            query = query.filter(
                or_(
                    MealRecurrenceRule.owner_id == user.id,
                    (MealRecurrenceRule.is_shared.is_(True))
                    & (MealRecurrenceRule.owner_id.in_(pantry_mate_ids)),
                )
            )
        else:
            query = query.filter(MealRecurrenceRule.owner_id == user.id)

        rules = query.order_by(MealRecurrenceRule.created_at.desc()).all()

        return success(
            data=ListRecurrenceRules.Response(
                items=[_rule_to_response(r) for r in rules],
                total=len(rules),
            )
        )

    class Response(BaseModel):
        items: list[RecurrenceRuleResponse]
        total: int
