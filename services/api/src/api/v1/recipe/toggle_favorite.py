"""Toggle recipe favorite endpoint.

rf-2: returns the full `GetRecipe.Response` with `is_favorite` nested
inside. Old clients that read only `is_favorite` keep working (the field
is still top-level on the response). New clients use the full payload to
patch their cached state without a round-trip.
"""

from api.v1.recipe._response import build_recipe_response
from api.v1.recipe.get_recipe import GetRecipe
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


class ToggleFavorite(Endpoint):
    """Toggle favorite status on a recipe."""

    def execute(self, recipe_id: str):
        """Toggle whether the current user has favorited a recipe."""
        user: User = self.user

        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        membership = self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=recipe.recipe_book_id,
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        existing = self.database.find_by(
            UserFavorite,
            user_id=user.id,
            recipe_id=recipe_id,
        )
        if existing:
            self.database.delete(existing)
            self.db.commit()
            status = 200
            new_is_favorite = False
        else:
            favorite = UserFavorite(
                user_id=user.id,
                recipe_id=recipe_id,
            )
            self.db.add(favorite)
            self.db.commit()
            status = 201
            new_is_favorite = True

        return success(
            data=build_recipe_response(
                self.database,
                user,
                recipe,
                can_edit=membership.role in ("owner", "editor"),
                is_favorite=new_is_favorite,
            ),
            status=status,
        )

    # Back-compat alias: callers referencing `ToggleFavorite.Response` for
    # OpenAPI / type hints now get the canonical recipe response.
    Response = GetRecipe.Response
