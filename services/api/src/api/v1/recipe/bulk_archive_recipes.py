"""Bulk archive recipes endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class BulkArchiveRecipes(Endpoint):
    """Archive multiple recipes at once."""

    def execute(self, params: "BulkArchiveRecipes.Params"):
        user: User = self.user

        if not params.recipe_ids:
            raise APIException(
                status_code=400,
                detail="No recipes specified",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Load and validate all recipes
        recipes = []
        for recipe_id in params.recipe_ids:
            recipe = self.database.find_by(Recipe, id=recipe_id)
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe not found: {recipe_id}",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )
            membership = self.database.find_by(
                RecipeBookUser,
                user_id=str(user.id),
                recipe_book_id=recipe.recipe_book_id,
            )
            if not membership or membership.role not in ("owner", "editor"):
                raise APIException(
                    status_code=403,
                    detail="You don't have permission to archive this recipe",
                    code=ErrorCode.RECIPE_ACCESS_DENIED,
                )
            recipes.append(recipe)

        # Perform archives
        now = datetime.now(UTC)
        for recipe in recipes:
            recipe.archived_at = now
        self.database.db.commit()

        return success(
            data=BulkArchiveRecipes.Response(archived_count=len(recipes))
        )

    class Params(BaseModel):
        recipe_ids: list[str] = Field(max_length=100)

    class Response(BaseModel):
        archived_count: int
