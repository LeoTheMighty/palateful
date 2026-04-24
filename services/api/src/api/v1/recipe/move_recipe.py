"""Move recipe to another book endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class MoveRecipe(AsyncEndpoint):
    """Move a recipe to a different recipe book."""

    async def execute(self, recipe_id: str, params: "MoveRecipe.Params"):
        """
        Move a recipe to a different book by updating recipe_book_id.

        Args:
            recipe_id: The recipe's ID
            params: Move parameters with destination_book_id

        Returns:
            Updated recipe ID and new book ID.
        """
        user: User = self.user

        # Get recipe
        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Check same book
        if str(recipe.recipe_book_id) == params.destination_book_id:
            raise APIException(
                status_code=400,
                detail="Recipe is already in this book",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Check source book access (owner/editor)
        src_membership = await self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=recipe.recipe_book_id,
        )
        if not src_membership or src_membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to move this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        # Check destination book exists
        dest_book = await self.database.find_by(RecipeBook, id=params.destination_book_id)
        if not dest_book:
            raise APIException(
                status_code=404,
                detail="Destination book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        # Check destination book access (owner/editor)
        dest_membership = await self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=params.destination_book_id,
        )
        if not dest_membership or dest_membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to add recipes to this book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Move recipe
        recipe.recipe_book_id = params.destination_book_id
        await self.database.db.commit()

        return success(
            data=MoveRecipe.Response(
                id=str(recipe.id),
                recipe_book_id=str(recipe.recipe_book_id),
            )
        )

    class Params(BaseModel):
        destination_book_id: str

    class Response(BaseModel):
        id: str
        recipe_book_id: str
