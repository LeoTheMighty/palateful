"""List recipes endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListRecipes(Endpoint):
    """List recipes in a recipe book."""

    def execute(
        self,
        book_id: str,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None
    ):
        """
        List recipes in a recipe book.

        Args:
            book_id: The recipe book's ID
            limit: Maximum number of results
            offset: Pagination offset
            search: Optional search query for recipe name

        Returns:
            Paginated list of recipes
        """
        user: User = self.user

        # Check access
        membership = self.database.find_by(
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

        # Build query
        query = self.db.query(Recipe).filter(Recipe.recipe_book_id == book_id)

        # Apply search filter
        if search:
            query = query.filter(Recipe.name.ilike(f"%{search}%"))

        # Get total count
        total = query.count()

        # Apply ordering and pagination
        recipes = (
            query
            .order_by(Recipe.name)
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            ListRecipes.RecipeItem(
                id=recipe.id,
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                image_url=recipe.image_url,
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
        created_at: datetime

    class Response(BaseModel):
        items: list["ListRecipes.RecipeItem"]
        total: int
        limit: int
        offset: int
