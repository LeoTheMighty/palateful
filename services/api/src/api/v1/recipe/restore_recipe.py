"""Restore archived recipe endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class RestoreRecipe(AsyncEndpoint):
    """Restore an archived recipe."""

    async def execute(self, recipe_id: str):
        """
        Restore an archived recipe by clearing archived_at.

        Args:
            recipe_id: The recipe's ID

        Returns:
            The restored recipe ID.
        """
        user: User = self.user

        # Must use include_archived=True to find archived recipes
        recipe = await self.database.find_by(Recipe, id=recipe_id, include_archived=True)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        if not recipe.is_archived():
            raise APIException(
                status_code=400,
                detail="Recipe is not archived",
                code=ErrorCode.RECIPE_NOT_ARCHIVED,
            )

        # Check ownership via RecipeBookUser
        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=recipe.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to restore this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        recipe.archived_at = None
        await self.database.db.commit()

        return success(data=RestoreRecipe.Response(id=str(recipe.id)))

    class Response(BaseModel):
        id: str
