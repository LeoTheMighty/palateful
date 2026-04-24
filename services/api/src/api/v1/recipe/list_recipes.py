"""List recipes endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


class ListRecipes(AsyncEndpoint):
    """List recipes in a recipe book."""

    async def execute(
        self,
        book_id: str,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
        vibe: str | None = None,
    ):
        """
        List recipes in a recipe book.

        Args:
            book_id: The recipe book's ID
            limit: Maximum number of results
            offset: Pagination offset
            search: Optional search query for recipe name
            vibe: Optional vibe filter (primary or secondary)

        Returns:
            Paginated list of recipes
        """
        user: User = self.user

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

        # Apply ordering and pagination
        list_result = await self.db.execute(
            stmt.order_by(Recipe.name).offset(offset).limit(limit)
        )
        recipes = list(list_result.scalars().all())

        # pbq-3 fast path: bulk favorite join — one SELECT over the page's
        # recipe_ids, not per-recipe round-trips.
        recipe_ids = [r.id for r in recipes]
        favorited_ids: set = set()
        if recipe_ids:
            fav_result = await self.db.execute(
                select(UserFavorite.recipe_id).where(
                    UserFavorite.user_id == user.id,
                    UserFavorite.recipe_id.in_(recipe_ids),
                )
            )
            favorited_ids = set(fav_result.scalars().all())

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
                created_at=recipe.created_at
            )
            for recipe in recipes
        ]

        return success(
            data=ListRecipes.Response(
                items=items,
                total=total,
                limit=limit,
                offset=offset
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

    class Response(BaseModel):
        items: list["ListRecipes.RecipeItem"]
        total: int
        limit: int
        offset: int
