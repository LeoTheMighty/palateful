"""Get recipe book endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.cooking_log import CookingLog
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class GetRecipeBook(AsyncEndpoint):
    """Get recipe book details by ID."""

    async def execute(self, recipe_book_id: str):
        """
        Get recipe book details including recipes and members.

        Args:
            recipe_book_id: The recipe book's ID

        Returns:
            Recipe book details with recipe list and member list
        """
        user: User = self.user

        # Check access
        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe_book_id
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED
            )

        # Side effect: update last_opened_at for recency sorting
        membership.last_opened_at = datetime.now(UTC)
        self.database.db.add(membership)
        await self.database.db.flush()

        # Get recipe book
        recipe_book = await self.database.find_by(RecipeBook, id=recipe_book_id)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail=f"Recipe book with ID '{recipe_book_id}' not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND
            )

        # Get recipes (exclude archived)
        recipes_result = await self.db.execute(
            select(Recipe)
            .where(
                Recipe.recipe_book_id == recipe_book_id,
                Recipe.archived_at.is_(None),
            )
            .order_by(Recipe.name.asc())
        )
        recipes = list(recipes_result.scalars().all())

        # recipe-list-org-1: bulk last_cooked aggregate over the embedded
        # recipes. The home-content provider in the Flutter app reads the
        # `recipes[]` payload here per book and feeds it into the same
        # table-view as ``GET /v1/recipe-books/{id}/recipes`` — so the
        # last_cooked field has to be on this shape too.
        last_cooked_by_recipe: dict = {}
        in_meal_ids: set = set()
        recipe_ids = [r.id for r in recipes]
        if recipe_ids:
            cooked_result = await self.db.execute(
                select(
                    CookingLog.recipe_id,
                    func.max(CookingLog.cooked_at),
                )
                .where(
                    CookingLog.recipe_id.in_(recipe_ids),
                    CookingLog.archived_at.is_(None),
                )
                .group_by(CookingLog.recipe_id)
            )
            for row in cooked_result.all():
                last_cooked_by_recipe[row[0]] = row[1]

            # recipe-list-org-2: meal-membership per recipe; joins through
            # `meals` so an archived meal stops hiding its recipes.
            in_meal_result = await self.db.execute(
                select(MealRecipe.recipe_id)
                .join(Meal, Meal.id == MealRecipe.meal_id)
                .where(
                    MealRecipe.recipe_id.in_(recipe_ids),
                    MealRecipe.archived_at.is_(None),
                    Meal.archived_at.is_(None),
                )
                .distinct()
            )
            in_meal_ids = set(in_meal_result.scalars().all())

        recipe_items = [
            GetRecipeBook.RecipeItem(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                image_url=recipe.image_url,
                created_at=recipe.created_at,
                updated_at=recipe.updated_at,
                last_cooked=last_cooked_by_recipe.get(recipe.id),
                is_in_meal=recipe.id in in_meal_ids,
            )
            for recipe in recipes
        ]
        total_in_meals = len(in_meal_ids)

        # Get all members with their user info
        members_result = await self.db.execute(
            select(RecipeBookUser, User)
            .join(User, RecipeBookUser.user_id == User.id)
            .where(
                RecipeBookUser.recipe_book_id == recipe_book_id,
                RecipeBookUser.archived_at.is_(None),
            )
        )
        all_memberships = members_result.all()
        members = [
            GetRecipeBook.MemberItem(
                user_id=str(rbu.user_id),
                name=u.name,
                role=rbu.role,
            )
            for rbu, u in all_memberships
        ]

        return success(
            data=GetRecipeBook.Response(
                id=str(recipe_book.id),
                name=recipe_book.name,
                description=recipe_book.description,
                is_public=recipe_book.is_public,
                is_shared=recipe_book.is_shared,
                is_system=recipe_book.is_system,
                user_role=membership.role,
                recipe_count=len(recipes),
                total_in_meals=total_in_meals,
                recipes=recipe_items,
                members=members,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            )
        )

    class RecipeItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        servings: int | None = None
        image_url: str | None = None
        created_at: datetime
        updated_at: datetime
        last_cooked: datetime | None = None
        is_in_meal: bool = False

    class MemberItem(BaseModel):
        user_id: str
        name: str | None = None
        role: str

    class Response(BaseModel):
        id: str
        name: str
        description: str | None = None
        is_public: bool = False
        is_shared: bool = False
        is_system: bool = False
        user_role: str = "owner"
        recipe_count: int = 0
        total_in_meals: int = 0
        recipes: list["GetRecipeBook.RecipeItem"] = []
        members: list["GetRecipeBook.MemberItem"] = []
        created_at: datetime
        updated_at: datetime
