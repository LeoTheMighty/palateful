"""Delete recipe book endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class DeleteRecipeBook(AsyncEndpoint):
    """Delete a recipe book."""

    async def execute(self, recipe_book_id: str):
        """
        Delete a recipe book and all its recipes.

        Args:
            recipe_book_id: The recipe book's ID

        Returns:
            Success response
        """
        user: User = self.user

        # Check access - must be owner
        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe_book_id
        )
        if not membership or membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the owner can delete a recipe book",
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

        # Auto-recovery: if deleting the default book, restore previous
        restored_default_id = None
        if str(recipe_book.id) == str(user.default_recipe_book_id or ""):
            user.default_recipe_book_id = user.previous_recipe_book_id
            user.previous_recipe_book_id = None
            restored_default_id = str(user.default_recipe_book_id) if user.default_recipe_book_id else None
            await self.database.db.flush()

        # Delete recipe book (cascades to recipes and memberships)
        await self.database.delete(recipe_book)

        return success(
            data=DeleteRecipeBook.Response(
                success=True,
                restored_default_recipe_book_id=restored_default_id,
            ),
            status=200
        )

    class Response(BaseModel):
        success: bool
        restored_default_recipe_book_id: str | None = None
