"""List favorite recipes endpoint.

md-3 extends the response with `favorited_meals` (additive key — pre-md-3
clients keep working off `items` / `total`). The meals payload reuses
foundation's `MealSummaryResponse` shape so the same widgets on the home
favorites carousel can render either type.
"""

from datetime import datetime

from api.v1.meal._response import build_meal_summary
from pydantic import BaseModel
from schemas.meal import MealSummaryResponse
from sqlalchemy.orm import selectinload
from utils.api.endpoint import Endpoint, success
from utils.models.meal import Meal
from utils.models.meal_favorite import MealFavorite
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


class ListFavorites(Endpoint):
    """List the current user's favorite recipes + Meals (md-3)."""

    def execute(self):
        user: User = self.user

        # Query recipe favorites joined with recipes, filtered by active membership
        results = (
            self.database.db.query(UserFavorite, Recipe)
            .join(Recipe, UserFavorite.recipe_id == Recipe.id)
            .join(RecipeBookUser, (
                (RecipeBookUser.recipe_book_id == Recipe.recipe_book_id)
                & (RecipeBookUser.user_id == user.id)
            ))
            .filter(UserFavorite.user_id == user.id)
            .filter(Recipe.archived_at.is_(None))
            .order_by(UserFavorite.created_at.desc())
            .all()
        )

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
        db = self.database.db
        meal_rows = (
            db.query(MealFavorite, Meal)
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
            .filter(MealFavorite.user_id == user.id)
            .filter(Meal.archived_at.is_(None))
            .order_by(MealFavorite.created_at.desc())
            .all()
        )

        favorited_meals = [
            build_meal_summary(meal, db=db, user_id=user.id)
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
