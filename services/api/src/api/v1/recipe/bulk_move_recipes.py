"""Bulk move recipes to another book endpoint."""

from pydantic import BaseModel, Field
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class BulkMoveRecipes(Endpoint):
    """Move multiple recipes to a different recipe book."""

    def execute(self, params: "BulkMoveRecipes.Params"):
        user: User = self.user

        if not params.recipe_ids:
            raise APIException(
                status_code=400,
                detail="No recipes specified",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Validate destination book exists and user has editor/owner access
        dest_book = self.database.find_by(RecipeBook, id=params.destination_book_id)
        if not dest_book:
            raise APIException(
                status_code=404,
                detail="Destination book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )
        dest_membership = self.database.find_by(
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
            # Skip recipes already in destination (idempotent)
            if str(recipe.recipe_book_id) == params.destination_book_id:
                continue
            src_membership = self.database.find_by(
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
            recipes.append(recipe)

        # Perform moves
        for recipe in recipes:
            recipe.recipe_book_id = params.destination_book_id
        self.database.db.commit()

        return success(
            data=BulkMoveRecipes.Response(moved_count=len(recipes))
        )

    class Params(BaseModel):
        recipe_ids: list[str] = Field(max_length=100)
        destination_book_id: str

    class Response(BaseModel):
        moved_count: int
