"""DELETE /v1/meals/{meal_id}/recipes/{recipe_id}."""

from api.v1.meal._access import require_meal_write
from api.v1.meal._response import build_meal_response
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.services.meal_service import (
    ComponentNotFoundError,
    MealService,
    MinComponentsError,
)


class RemoveRecipeFromMeal(AsyncEndpoint):
    """Detach a component from a Meal. Rejects if it would leave <2."""

    async def execute(self, meal_id: str, recipe_id: str):
        user: User = self.user
        db = self.db

        meal = await require_meal_write(db, meal_id, user)
        service = MealService(db)

        try:
            await service.remove_component(meal=meal, recipe_id=recipe_id)
        except MinComponentsError as exc:
            raise APIException(
                status_code=422,
                detail=(
                    "A meal needs at least 2 recipes. Remove this one "
                    "only after adding a replacement."
                ),
                code=ErrorCode.MEAL_MIN_COMPONENTS,
            ) from exc
        except ComponentNotFoundError as exc:
            raise APIException(
                status_code=404,
                detail="Component not found on this meal",
                code=ErrorCode.MEAL_COMPONENT_NOT_FOUND,
            ) from exc

        meal = await service.get_with_components(meal_id)
        await db.commit()
        return success(
            data=await build_meal_response(meal, db=db, user_id=user.id)
        )
