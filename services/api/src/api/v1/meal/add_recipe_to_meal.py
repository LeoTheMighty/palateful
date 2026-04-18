"""POST /v1/meals/{meal_id}/recipes — add a component."""

from api.v1.meal._access import require_meal_write
from api.v1.meal._response import build_meal_response
from schemas.meal import MealComponentAddRequest
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.services.meal_service import (
    ComponentDuplicateError,
    ComponentUnreadableError,
    MealService,
)


class AddRecipeToMeal(Endpoint):
    """Attach an additional component to a Meal."""

    def execute(self, meal_id: str, params: MealComponentAddRequest):
        user: User = self.user
        db = self.db

        meal = require_meal_write(db, meal_id, user)
        service = MealService(db)

        try:
            service.add_component(
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
            raise APIException(
                status_code=404,
                detail="Recipe not readable",
                code=ErrorCode.MEAL_COMPONENT_UNREADABLE,
            ) from exc

        meal = service.get_with_components(meal_id)
        db.commit()
        return success(
            data=build_meal_response(meal, db=db, user_id=user.id),
            status=201,
        )
