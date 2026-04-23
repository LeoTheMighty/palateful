"""Create Meal endpoint — POST /v1/recipe-books/{book_id}/meals."""

from api.v1.meal._access import require_book_write
from api.v1.meal._response import build_meal_response
from schemas.meal import MealCreateRequest
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.user import User
from utils.services.meal_service import ComponentUnreadableError, MealService


class CreateMeal(AsyncEndpoint):
    """Create a Meal + its component joins in a single transaction."""

    async def execute(self, book_id: str, params: MealCreateRequest):
        user: User = self.user
        db = self.db

        await require_book_write(db, book_id, user)

        service = MealService(db)
        try:
            meal = await service.create_with_components(
                book_id=book_id,
                name=params.name,
                description=params.description,
                recipe_ids=params.component_recipe_ids,
                user_id=user.id,
            )
        except ComponentUnreadableError as exc:
            raise APIException(
                status_code=404,
                detail="One or more component recipes are not readable",
                code=ErrorCode.MEAL_COMPONENT_UNREADABLE,
            ) from exc

        # Re-fetch with selectinload chain so the response hydrates cleanly.
        meal = await service.get_with_components(str(meal.id))
        await db.commit()

        return success(
            data=await build_meal_response(meal, db=db, user_id=user.id),
            status=201,
        )
