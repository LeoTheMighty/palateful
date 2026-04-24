"""Generate a public share token for a recipe.

aam-12a: converted to AsyncEndpoint.
"""

import secrets

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ShareRecipe(AsyncEndpoint):
    """Generate a public share link token for a recipe."""

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
                detail="You don't have permission to share this recipe",
                code=ErrorCode.FORBIDDEN,
            )

        token = secrets.token_urlsafe(15)
        recipe.share_token = token
        await self.db.commit()
        await self.db.refresh(recipe)

        return success(
            data=ShareRecipe.Response(
                token=token,
                deep_link=f"palateful://recipe-public/{token}",
            ),
            status=201,
        )

    class Response(BaseModel):
        token: str
        deep_link: str
