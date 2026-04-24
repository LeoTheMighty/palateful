"""List favorite recipes endpoint.

md-3 extends the response with `favorited_meals` (additive key — pre-md-3
clients keep working off `items` / `total`). The meals payload reuses
foundation's `MealSummaryResponse` shape so the same widgets on the home
favorites carousel can render either type.

aam-10 cross-domain conversion: this recipe-domain handler depends on
`api.v1.meal._response.build_meal_summary`, which became `async` when the
meal domain converted. Keeping this endpoint sync would call the async
builder without `await` and stuff a coroutine into `MealSummaryResponse`,
breaking response validation in prod. Converted to `AsyncEndpoint` here
so the recipe domain isn't blocked by aam-10's blast radius.
"""

from datetime import datetime

from api.v1.meal._response import build_meal_summary
from pydantic import BaseModel
from schemas.meal import MealSummaryResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.meal import Meal
from utils.models.meal_favorite import MealFavorite
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


class ListFavorites(AsyncEndpoint):
    """List the current user's favorite recipes + Meals (md-3)."""

    async def execute(self):
        user: User = self.user
        db = self.db

        recipe_stmt = (
            select(UserFavorite, Recipe)
            .join(Recipe, UserFavorite.recipe_id == Recipe.id)
            .join(RecipeBookUser, (
                (RecipeBookUser.recipe_book_id == Recipe.recipe_book_id)
                & (RecipeBookUser.user_id == user.id)
            ))
            .where(UserFavorite.user_id == user.id)
            .where(Recipe.archived_at.is_(None))
            .order_by(UserFavorite.created_at.desc())
        )
        recipe_result = await db.execute(recipe_stmt)
        results = list(recipe_result.all())

        items = [
            ListFavorites.FavoriteItem(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                image_url=recipe.image_url,
                tags=recipe.tags or [],
                primary_vibe=recipe.primary_vibe,
                secondary_vibe=recipe.secondary_vibe,
                is_favorite=True,
                created_at=recipe.created_at,
            )
            for _fav, recipe in results
        ]

        # md-3: include favorited Meals as an additive response key.
        # Only Meals the user can still read + that aren't archived.
        meal_stmt = (
            select(MealFavorite, Meal)
            .join(Meal, MealFavorite.meal_id == Meal.id)
            .join(RecipeBookUser, (
                (RecipeBookUser.recipe_book_id == Meal.recipe_book_id)
                & (RecipeBookUser.user_id == user.id)
                & (RecipeBookUser.archived_at.is_(None))
            ))
            .options(
                selectinload(Meal.components)
                .selectinload(MealRecipe.recipe)
                .selectinload(Recipe.recipe_book)
            )
            .where(MealFavorite.user_id == user.id)
            .where(Meal.archived_at.is_(None))
            .order_by(MealFavorite.created_at.desc())
        )
        meal_result = await db.execute(meal_stmt)
        meal_rows = list(meal_result.all())

        favorited_meals = [
            await build_meal_summary(meal, db=db, user_id=user.id)
            for _fav, meal in meal_rows
        ]

        return success(
            data=ListFavorites.Response(
                items=items,
                total=len(items),
                favorited_meals=favorited_meals,
            )
        )

    class FavoriteItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        servings: int | None = None
        image_url: str | None = None
        tags: list[str] = []
        primary_vibe: str | None = None
        secondary_vibe: str | None = None
        is_favorite: bool = True
        created_at: datetime

    class Response(BaseModel):
        items: list["ListFavorites.FavoriteItem"]
        total: int
        favorited_meals: list[MealSummaryResponse] = []
