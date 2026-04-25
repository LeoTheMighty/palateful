"""Update recipe book endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class UpdateRecipeBook(AsyncEndpoint):
    """Update a recipe book."""

    async def execute(self, recipe_book_id: str, params: "UpdateRecipeBook.Params"):
        """
        Update a recipe book.

        Args:
            recipe_book_id: The recipe book's ID
            params: Update parameters

        Returns:
            Updated recipe book data
        """
        user: User = self.user

        # Check access - must be owner or editor
        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe_book_id
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to edit this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED
            )

        # Get recipe book
        recipe_book = await self.database.find_by(RecipeBook, id=recipe_book_id)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail=f"Recipe book with ID '{recipe_book_id}' not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND
            )

        if recipe_book.is_system:
            raise APIException(
                status_code=400,
                detail="Cannot modify a system recipe book",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Only owners can change is_public
        if params.is_public is not None and membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the owner can change public visibility",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED
            )

        # Build update dict
        updates = {}
        if params.name is not None:
            updates["name"] = params.name
        if params.description is not None:
            updates["description"] = params.description
        if params.is_public is not None:
            updates["is_public"] = params.is_public

        # Update if there are changes
        if updates:
            await self.database.update(recipe_book, **updates)

        # Get recipe count
        count_result = await self.db.execute(
            select(func.count(Recipe.id)).where(
                Recipe.recipe_book_id == recipe_book_id
            )
        )
        recipe_count = count_result.scalar() or 0

        return success(
            data=UpdateRecipeBook.Response(
                id=recipe_book.id,
                name=recipe_book.name,
                description=recipe_book.description,
                is_public=recipe_book.is_public,
                recipe_count=recipe_count,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            )
        )

    class Params(BaseModel):
        name: str | None = None
        description: str | None = None
        is_public: bool | None = None

    class Response(BaseModel):
        id: str
        name: str
        description: str | None = None
        is_public: bool = False
        recipe_count: int
        created_at: datetime
        updated_at: datetime
