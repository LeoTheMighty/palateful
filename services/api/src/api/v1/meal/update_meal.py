"""PATCH /v1/meals/{meal_id} — name + description only."""

from api.v1.meal._access import require_meal_write
from api.v1.meal._response import build_meal_response
from schemas.meal import MealUpdateRequest
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.user import User


class UpdateMeal(AsyncEndpoint):
    """Update a Meal's name / description. Component changes go through
    the add/remove/reorder endpoints."""

    async def execute(self, meal_id: str, params: MealUpdateRequest):
        user: User = self.user
        db = self.db

        meal = await require_meal_write(db, meal_id, user)

        if params.name is not None:
            meal.name = params.name
        if params.description is not None:
            meal.description = params.description

        await db.flush()
        await db.commit()
        return success(
            data=await build_meal_response(meal, db=db, user_id=user.id)
        )
