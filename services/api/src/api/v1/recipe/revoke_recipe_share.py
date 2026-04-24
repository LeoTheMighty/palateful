"""Revoke a recipe's public share token.

aam-12a: converted to AsyncEndpoint.
"""

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class RevokeRecipeShare(AsyncEndpoint):
    """Revoke the public share link for a recipe."""

    async def execute(self, recipe_id: str):
        user: User = self.user

        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to revoke sharing for this recipe",
                code=ErrorCode.FORBIDDEN,
            )

        recipe.share_token = None
        await self.db.commit()

        return success(data=RevokeRecipeShare.Response(success=True))

    class Response(BaseModel):
        success: bool
