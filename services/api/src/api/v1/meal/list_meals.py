"""GET /v1/meals — flat list across every readable book."""

from api.v1.meal._response import build_meal_summary
from schemas.meal import MealListResponse
from sqlalchemy.orm import selectinload
from utils.api.endpoint import Endpoint, success
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListMeals(Endpoint):
    """List Meals across every book the user can read."""

    def execute(
        self,
        limit: int = 20,
        offset: int = 0,
        include_archived: bool = False,
    ):
        user: User = self.user
        db = self.db

        readable_books = (
            db.query(RecipeBookUser.recipe_book_id)
            .filter(
                RecipeBookUser.user_id == user.id,
                RecipeBookUser.archived_at.is_(None),
            )
            .subquery()
        )

        query = (
            db.query(Meal)
            .options(
                selectinload(Meal.components)
                .selectinload(MealRecipe.recipe)
                .selectinload(Recipe.recipe_book)
            )
            .filter(Meal.recipe_book_id.in_(readable_books))
        )
        if not include_archived:
            query = query.filter(Meal.archived_at.is_(None))

        total = query.count()
        meals = (
            query.order_by(Meal.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            build_meal_summary(m, db=db, user_id=user.id) for m in meals
        ]
        return success(data=MealListResponse(items=items, total=total))
