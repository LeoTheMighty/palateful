"""Get a single recipe version snapshot endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_version import RecipeVersion
from utils.models.user import User


class GetRecipeVersion(Endpoint):
    """Get the full snapshot for a specific recipe version."""

    def execute(self, recipe_id: str, version_id: str):
        """
        Get a single version snapshot by ID.

        Args:
            recipe_id: The recipe's ID
            version_id: The version's ID

        Returns:
            Full version snapshot including all recipe fields at that point in time
        """
        user: User = self.user

        # Get recipe
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND
            )

        # Check access via recipe book membership
        membership = self.database.find_by(
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

        # Get the specific version
        version = self.database.find_by(RecipeVersion, id=version_id)
        if not version or str(version.recipe_id) != str(recipe_id):
            raise APIException(
                status_code=404,
                detail=f"Version with ID '{version_id}' not found for this recipe",
                code=ErrorCode.NOT_FOUND
            )

        return success(
            data=GetRecipeVersion.Response(
                id=str(version.id),
                version_number=version.version_number,
                snapshot=version.snapshot,
                changed_fields=version.changed_fields or [],
                created_at=version.created_at,
            )
        )

    class Response(BaseModel):
        id: str
        version_number: int
        snapshot: dict
        changed_fields: list[str] = []
        created_at: datetime
