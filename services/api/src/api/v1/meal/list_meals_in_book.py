"""GET /v1/recipe-books/{book_id}/meals."""

from api.v1.meal._response import build_meal_summary
from schemas.meal import MealListResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListMealsInBook(AsyncEndpoint):
    """List Meals in a single recipe_book."""

    async def execute(
        self,
        book_id: str,
        limit: int = 20,
        offset: int = 0,
        include_archived: bool = False,
    ):
        user: User = self.user
        db = self.db

        # Read-level membership suffices for list; reuse the write helper's
        # base check by looking up a generic membership row directly —
        # keeps this handler independent of mutation helpers.
        membership_result = await db.execute(
            select(RecipeBookUser).where(
                RecipeBookUser.user_id == user.id,
                RecipeBookUser.recipe_book_id == book_id,
                RecipeBookUser.archived_at.is_(None),
            )
        )
        membership = membership_result.scalars().first()
        if membership is None:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        conditions = [Meal.recipe_book_id == book_id]
        if not include_archived:
            conditions.append(Meal.archived_at.is_(None))

        count_stmt = (
            select(func.count()).select_from(Meal).where(*conditions)
        )
        total_result = await db.execute(count_stmt)
        total = int(total_result.scalar_one())

        meals_stmt = (
            select(Meal)
            .options(
                selectinload(Meal.components)
                .selectinload(MealRecipe.recipe)
                .selectinload(Recipe.recipe_book)
            )
            .where(*conditions)
            .order_by(Meal.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        meals_result = await db.execute(meals_stmt)
        meals = list(meals_result.scalars().all())

        items = [
            await build_meal_summary(m, db=db, user_id=user.id) for m in meals
        ]
        return success(data=MealListResponse(items=items, total=total))
