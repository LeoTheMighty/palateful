"""md-2: reverse-lookup `GET /v1/recipes/{recipe_id}/meals`.

Returns every Meal that the current user can read AND that references
the given recipe as a component. Cross-book visibility is deliberate:
if Leo can read Book A (where the recipe lives) and Book B (where the
Meal lives), the Meal surfaces even though the Meal's book differs
from the recipe's book.

Two queries total regardless of result size: one for the Meal list,
one selectinload for the component hydration used by the MealSummary
shaper.

aam-10 cross-domain conversion: this recipe-domain handler depends on
`api.v1.meal._response.build_meal_summary`, which became `async` when
the meal domain converted. Converted to `AsyncEndpoint` here so the
recipe domain isn't blocked by aam-10's blast radius.
"""

from api.v1.meal._response import build_meal_summary
from pydantic import BaseModel
from schemas.meal import MealSummaryResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListMealsUsingRecipe(AsyncEndpoint):
    """List Meals referencing a given recipe — the "Used in these Meals" row."""

    async def execute(self, recipe_id: str):
        user: User = self.user
        db = self.db

        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if recipe is None:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Must be able to read the recipe's book. Archived-but-readable
        # recipes still count — users may legitimately want to see that
        # an archived Dressing was once part of a Kale Salad Meal.
        recipe_membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id,
        )
        if recipe_membership is None:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        readable_books_subq = (
            select(RecipeBookUser.recipe_book_id)
            .where(
                RecipeBookUser.user_id == user.id,
                RecipeBookUser.archived_at.is_(None),
            )
            .subquery()
        )

        meals_stmt = (
            select(Meal)
            .join(MealRecipe, MealRecipe.meal_id == Meal.id)
            .options(
                selectinload(Meal.components)
                .selectinload(MealRecipe.recipe)
                .selectinload(Recipe.recipe_book)
            )
            .where(
                MealRecipe.recipe_id == recipe_id,
                Meal.archived_at.is_(None),
                Meal.recipe_book_id.in_(select(readable_books_subq)),
            )
            .order_by(Meal.updated_at.desc())
        )
        meals_result = await db.execute(meals_stmt)
        meals = list(meals_result.scalars().all())

        items = [
            await build_meal_summary(m, db=db, user_id=user.id) for m in meals
        ]
        return success(data=ListMealsUsingRecipe.Response(items=items))

    class Response(BaseModel):
        items: list[MealSummaryResponse] = []
