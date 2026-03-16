"""Delete (archive) recipe endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class DeleteRecipe(Endpoint):
    """Delete (archive) a recipe via soft delete."""

    def execute(self, recipe_id: str):
        """
        Archive a recipe by setting archived_at.

        Args:
            recipe_id: The recipe's ID

        Returns:
            Success response
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

        # Check access - must be owner or editor
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=recipe.recipe_book_id
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to delete this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED
            )

        # Soft delete by setting archived_at
        recipe.archived_at = datetime.now(UTC)
        self.database.db.commit()

        return success(
            data=DeleteRecipe.Response(success=True),
            status=200
        )

    class Response(BaseModel):
        success: bool
