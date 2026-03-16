"""Toggle recipe favorite endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


class ToggleFavorite(Endpoint):
    """Toggle favorite status on a recipe."""

    def execute(self, recipe_id: str):
        """
        Toggle whether the current user has favorited a recipe.

        Args:
            recipe_id: The recipe's ID.

        Returns:
            The new favorite status.
        """
        user: User = self.user

        # Verify recipe exists
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Verify user has access via recipe book membership
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id,
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        # Check if already favorited
        existing = self.database.find_by(
            UserFavorite,
            user_id=user.id,
            recipe_id=recipe_id,
        )

        if existing:
            # Unfavorite
            self.database.delete(existing)
            self.db.flush()
            return success(
                data=ToggleFavorite.Response(is_favorite=False)
            )
        else:
            # Favorite
            favorite = UserFavorite(
                user_id=user.id,
                recipe_id=recipe_id,
            )
            self.db.add(favorite)
            self.db.flush()
            return success(
                data=ToggleFavorite.Response(is_favorite=True),
                status=201,
            )

    class Response(BaseModel):
        is_favorite: bool
