"""List recipes endpoint."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.cooking_log import CookingLog
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_favorite import UserFavorite

# recipe-list-org-1: keep these tight — every accepted value needs an
# arm in the order-by builder + a unit test, otherwise the api 100%
# coverage gate trips on the next push.
_ALLOWED_SORTS: tuple[str, ...] = ("name", "created_at", "last_cooked")
_ALLOWED_DIRS: tuple[str, ...] = ("asc", "desc")


class ListRecipes(AsyncEndpoint):
    """List recipes in a recipe book."""

    async def execute(
        self,
        book_id: str,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        vibe: str | None = None,
        sort: str = "name",
        dir: str = "asc",
    ):
        """
        List recipes in a recipe book.

        Args:
            book_id: The recipe book's ID
            limit: Maximum number of results
            offset: Pagination offset
            search: Optional search query for recipe name
            vibe: Optional vibe filter (primary or secondary)
            sort: Sort key — one of ``name`` (default), ``created_at``,
                ``last_cooked``.
            dir: Sort direction — ``asc`` (default) or ``desc``. ``last_cooked``
                always sorts ``NULLS LAST`` on desc and ``NULLS FIRST`` on asc
                (recipes never cooked sink to the bottom on the user's
                "most-recently cooked first" view).

        Returns:
            Paginated list of recipes
        """
        user: User = self.user

        if sort not in _ALLOWED_SORTS:
            raise APIException(
                status_code=400,
                detail=f"Invalid sort '{sort}'. Allowed: {', '.join(_ALLOWED_SORTS)}.",
                code=ErrorCode.INVALID_REQUEST,
            )
        if dir not in _ALLOWED_DIRS:
            raise APIException(
                status_code=400,
                detail=f"Invalid dir '{dir}'. Allowed: {', '.join(_ALLOWED_DIRS)}.",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Check access
        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=book_id
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED
            )

        # Build query (exclude archived recipes)
        stmt = select(Recipe).where(
            Recipe.recipe_book_id == book_id,
            Recipe.archived_at.is_(None),
        )

        # Apply search filter
        if search:
            stmt = stmt.where(Recipe.name.ilike(f"%{search}%"))

        # Apply vibe filter
        if vibe:
            stmt = stmt.where(
                or_(Recipe.primary_vibe == vibe, Recipe.secondary_vibe == vibe)
            )

        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        )
        total = int(count_result.scalar_one())

        # recipe-list-org-2: total_in_meals — distinct count of recipes in
        # this book that are referenced by a non-archived meal_recipes row
        # whose parent meal is also non-archived. Same predicate the
        # per-row is_in_meal aggregate uses below — keeps the chip count
        # consistent with the row flags across pagination.
        total_in_meals_result = await self.db.execute(
            select(func.count(func.distinct(MealRecipe.recipe_id)))
            .select_from(MealRecipe)
            .join(Meal, Meal.id == MealRecipe.meal_id)
            .join(Recipe, Recipe.id == MealRecipe.recipe_id)
            .where(
                Recipe.recipe_book_id == book_id,
                Recipe.archived_at.is_(None),
                MealRecipe.archived_at.is_(None),
                Meal.archived_at.is_(None),
            )
        )
        total_in_meals = int(total_in_meals_result.scalar_one() or 0)

        # Apply ordering. last_cooked sorts via a correlated scalar
        # subquery on cooking_logs — the ix_cooking_logs_recipe_id_cooked_at_active
        # partial index serves this directly.
        stmt = _apply_order(stmt, sort, dir)

        list_result = await self.db.execute(
            stmt.offset(offset).limit(limit)
        )
        recipes = list(list_result.scalars().all())

        # pbq-3 fast path: bulk favorite join — one SELECT over the page's
        # recipe_ids, not per-recipe round-trips.
        recipe_ids = [r.id for r in recipes]
        favorited_ids: set = set()
        last_cooked_by_recipe: dict = {}
        in_meal_ids: set = set()
        if recipe_ids:
            fav_result = await self.db.execute(
                select(UserFavorite.recipe_id).where(
                    UserFavorite.user_id == user.id,
                    UserFavorite.recipe_id.in_(recipe_ids),
                )
            )
            favorited_ids = set(fav_result.scalars().all())

            # recipe-list-org-1: bulk last_cooked aggregate. One round-trip
            # per page, not per recipe. The partial index keeps this an
            # index-only scan even on cold cache.
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

            # recipe-list-org-2: bulk meal-membership lookup. Joins through
            # `meals` so an archived meal stops hiding its recipes — the
            # join row survives soft-archive but the parent meal is gated
            # out by archived_at IS NULL.
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

        items = [
            ListRecipes.RecipeItem(
                id=recipe.id,
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                image_url=recipe.image_url,
                tags=recipe.tags or [],
                primary_vibe=recipe.primary_vibe,
                secondary_vibe=recipe.secondary_vibe,
                is_favorite=recipe.id in favorited_ids,
                created_at=recipe.created_at,
                last_cooked=last_cooked_by_recipe.get(recipe.id),
                is_in_meal=recipe.id in in_meal_ids,
            )
            for recipe in recipes
        ]

        return success(
            data=ListRecipes.Response(
                items=items,
                total=total,
                total_in_meals=total_in_meals,
                limit=limit,
                offset=offset,
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
        tags: list[str] = []
        primary_vibe: str | None = None
        secondary_vibe: str | None = None
        is_favorite: bool = False
        created_at: datetime
        last_cooked: datetime | None = None
        is_in_meal: bool = False

    class Response(BaseModel):
        items: list["ListRecipes.RecipeItem"]
        total: int
        total_in_meals: int = 0
        limit: int
        offset: int


def _apply_order(stmt, sort: str, direction: Literal["asc", "desc"]):
    """Append the right ORDER BY clause for the (sort, direction) pair.

    last_cooked sorts via a correlated scalar subquery on cooking_logs.
    NULLS handling is opinionated: never-cooked recipes sink to the bottom
    on desc (the user's "show me the most recently cooked first" lens) and
    rise to the top on asc.
    """
    if sort == "last_cooked":
        last_cooked_subq = (
            select(func.max(CookingLog.cooked_at))
            .where(
                CookingLog.recipe_id == Recipe.id,
                CookingLog.archived_at.is_(None),
            )
            .correlate(Recipe)
            .scalar_subquery()
        )
        if direction == "desc":
            return stmt.order_by(last_cooked_subq.desc().nulls_last())
        return stmt.order_by(last_cooked_subq.asc().nulls_first())

    col = Recipe.created_at if sort == "created_at" else Recipe.name
    return stmt.order_by(col.desc() if direction == "desc" else col.asc())
