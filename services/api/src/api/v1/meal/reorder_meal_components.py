"""POST /v1/meals/{meal_id}/reorder."""

from api.v1.meal._access import require_meal_write
from api.v1.meal._response import build_meal_response
from schemas.meal import MealReorderRequest
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.services.meal_service import MealService, ReorderMismatchError


class ReorderMealComponents(AsyncEndpoint):
    """Atomically rewrite order_index for every component on a Meal."""

    async def execute(self, meal_id: str, params: MealReorderRequest):
        user: User = self.user
        db = self.db

        meal = await require_meal_write(db, meal_id, user)
        service = MealService(db)

        try:
            await service.reorder_components(
                meal=meal, recipe_ids=params.recipe_ids
            )
        except ReorderMismatchError as exc:
            raise APIException(
                status_code=422,
                detail=(
                    "Reorder list must contain exactly the current "
                    "components"
                ),
                code=ErrorCode.MEAL_REORDER_MISMATCH,
            ) from exc

        meal = await service.get_with_components(meal_id)
        await db.commit()
        return success(
            data=await build_meal_response(meal, db=db, user_id=user.id)
        )
