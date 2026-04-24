"""Get recipe version history endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_version import RecipeVersion
from utils.models.user import User


class GetRecipeVersions(AsyncEndpoint):
    """List version history for a recipe."""

    async def execute(self, recipe_id: str):
        """
        Get version history for a recipe (without full snapshots).

        Args:
            recipe_id: The recipe's ID

        Returns:
            List of version summaries
        """
        user: User = self.user

        # Get recipe
        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND
            )

        # Check access via recipe book
        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED
            )

        # Fetch versions ordered by version number descending (newest first)
        versions = await self.database.where(
            RecipeVersion,
            desc="version_number",
            recipe_id=recipe_id,
        ).all()

        version_responses = [
            GetRecipeVersions.VersionSummary(
                id=str(v.id),
                version_number=v.version_number,
                changed_fields=v.changed_fields or [],
                created_at=v.created_at,
            )
            for v in versions
        ]

        return success(
            data=GetRecipeVersions.Response(
                recipe_id=str(recipe.id),
                versions=version_responses,
                total=len(version_responses),
            )
        )

    class VersionSummary(BaseModel):
        id: str
        version_number: int
        changed_fields: list[str] = []
        created_at: datetime

    class Response(BaseModel):
        recipe_id: str
        versions: list["GetRecipeVersions.VersionSummary"] = []
        total: int = 0
