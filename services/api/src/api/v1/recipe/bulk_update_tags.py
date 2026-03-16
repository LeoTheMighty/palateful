"""Bulk update tags on recipes endpoint."""

from pydantic import BaseModel, Field
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class BulkUpdateTags(Endpoint):
    """Add or remove tags on multiple recipes at once."""

    def execute(self, params: "BulkUpdateTags.Params"):
        user: User = self.user

        if not params.recipe_ids:
            raise APIException(
                status_code=400,
                detail="No recipes specified",
                code=ErrorCode.INVALID_REQUEST,
            )
        if not params.add_tags and not params.remove_tags:
            raise APIException(
                status_code=400,
                detail="No tag changes specified",
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
                    detail="You don't have permission to edit this recipe",
                    code=ErrorCode.RECIPE_ACCESS_DENIED,
                )
            recipes.append(recipe)

        # Apply tag changes
        for recipe in recipes:
            current_tags = list(recipe.tags) if recipe.tags else []
            # Add new tags (deduplicate)
            for tag in params.add_tags:
                if tag not in current_tags:
                    current_tags.append(tag)
            # Remove tags
            current_tags = [t for t in current_tags if t not in params.remove_tags]
            recipe.tags = current_tags
        self.database.db.commit()

        return success(
            data=BulkUpdateTags.Response(updated_count=len(recipes))
        )

    class Params(BaseModel):
        recipe_ids: list[str] = Field(max_length=100)
        add_tags: list[str] = []
        remove_tags: list[str] = []

    class Response(BaseModel):
        updated_count: int
