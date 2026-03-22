"""Archive recipe book endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ArchiveRecipeBook(Endpoint):
    """Archive a recipe book via soft delete."""

    def execute(self, recipe_book_id: str):
        user: User = self.user

        # Check access - must be owner
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=recipe_book_id,
        )
        if not membership or membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the owner can archive a recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Get recipe book (include archived to give proper "already archived" error)
        recipe_book = self.database.find_by(RecipeBook, id=recipe_book_id, include_archived=True)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail="Recipe book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        if recipe_book.is_archived():
            raise APIException(
                status_code=400,
                detail="Recipe book is already archived",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Auto-recovery: if archiving the default book, restore previous
        restored_default_id = None
        if str(recipe_book.id) == str(user.default_recipe_book_id or ""):
            user.default_recipe_book_id = user.previous_recipe_book_id
            user.previous_recipe_book_id = None
            restored_default_id = str(user.default_recipe_book_id) if user.default_recipe_book_id else None

        recipe_book.archived_at = datetime.now(UTC)
        self.database.db.commit()

        return success(data=ArchiveRecipeBook.Response(
            success=True,
            restored_default_recipe_book_id=restored_default_id,
        ))

    class Response(BaseModel):
        success: bool
        restored_default_recipe_book_id: str | None = None
