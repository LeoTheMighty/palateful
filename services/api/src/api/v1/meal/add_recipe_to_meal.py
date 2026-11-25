"""POST /v1/meals/{meal_id}/recipes — add a component."""

from api.v1.meal._access import require_meal_write
from api.v1.meal._response import build_meal_response
from schemas.meal import MealComponentAddRequest
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.services.meal_service import (
    ComponentDuplicateError,
    ComponentUnreadableError,
    MealService,
)


class AddRecipeToMeal(AsyncEndpoint):
    """Attach an additional component to a Meal."""

    async def execute(self, meal_id: str, params: MealComponentAddRequest):
        user: User = self.user
        db = self.db

        meal = await require_meal_write(db, meal_id, user)
        service = MealService(db)

        try:
            await service.add_component(
                meal=meal,
                recipe_id=params.recipe_id,
                order_index=params.order_index,
                user_id=user.id,
            )
        except ComponentDuplicateError as exc:
            raise APIException(
                status_code=409,
                detail="This recipe is already on the meal",
                code=ErrorCode.MEAL_COMPONENT_DUPLICATE,
            ) from exc
        except ComponentUnreadableError as exc:
            # btri01: same contract as CreateMeal — the edit-mode picker
            # needs the id to mark the row, not just a banner.
            raise APIException(
                status_code=404,
                detail="Recipe not readable",
                code=ErrorCode.MEAL_COMPONENT_UNREADABLE,
                data={"recipe_ids": list(exc.recipe_ids)},
            ) from exc

        meal = await service.get_with_components(meal_id)
        await db.commit()
        return success(
            data=await build_meal_response(meal, db=db, user_id=user.id),
            status=201,
        )
