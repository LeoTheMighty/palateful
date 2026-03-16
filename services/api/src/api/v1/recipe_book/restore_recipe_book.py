"""Restore archived recipe book endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class RestoreRecipeBook(Endpoint):
    """Restore an archived recipe book."""

    def execute(self, recipe_book_id: str):
        user: User = self.user

        # Must use include_archived=True to find archived books
        recipe_book = self.database.find_by(
            RecipeBook, id=recipe_book_id, include_archived=True
        )
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail="Recipe book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        if not recipe_book.is_archived():
            raise APIException(
                status_code=400,
                detail="Recipe book is not archived",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Check access - must be owner
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=recipe_book_id,
        )
        if not membership or membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the owner can restore a recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        recipe_book.archived_at = None
        self.database.db.commit()

        return success(data=RestoreRecipeBook.Response(id=str(recipe_book.id)))

    class Response(BaseModel):
        id: str
