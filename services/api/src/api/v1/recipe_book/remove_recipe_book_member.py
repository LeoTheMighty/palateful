"""Remove member from recipe book endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class RemoveRecipeBookMember(Endpoint):
    """Remove a member from a recipe book (owner only)."""

    def execute(self, recipe_book_id: str, target_user_id: str):
        user: User = self.user

        # Only owners can remove members
        caller_membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe_book_id,
        )
        if not caller_membership or caller_membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the owner can remove members from this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Prevent owner self-removal
        if str(user.id) == str(target_user_id):
            raise APIException(
                status_code=400,
                detail="Owner cannot remove themselves from the recipe book",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Find the target membership
        target_membership = self.database.find_by(
            RecipeBookUser,
            user_id=target_user_id,
            recipe_book_id=recipe_book_id,
        )
        if not target_membership:
            raise APIException(
                status_code=404,
                detail="Member not found in this recipe book",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        self.database.delete(target_membership)

        return success(data=RemoveRecipeBookMember.Response(success=True))

    class Response(BaseModel):
        success: bool
