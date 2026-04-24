"""Update a recipe book member's role endpoint."""

from pydantic import BaseModel, model_validator
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class UpdateRecipeBookMemberRole(AsyncEndpoint):
    """Update a member's role in a recipe book (owner only)."""

    async def execute(
        self,
        recipe_book_id: str,
        target_user_id: str,
        params: "UpdateRecipeBookMemberRole.Params",
    ):
        user: User = self.user

        # Only owners can update roles
        caller_membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe_book_id,
        )
        if not caller_membership or caller_membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the owner can update member roles",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Prevent owner from changing their own role
        if str(user.id) == str(target_user_id):
            raise APIException(
                status_code=400,
                detail="Owner cannot change their own role",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Find the target membership
        target_membership = await self.database.find_by(
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

        await self.database.update(target_membership, role=params.role)

        return success(
            data=UpdateRecipeBookMemberRole.Response(
                user_id=str(target_membership.user_id),
                role=params.role,
            )
        )

    class Params(BaseModel):
        role: str

        @model_validator(mode="after")
        def validate_role(self) -> "UpdateRecipeBookMemberRole.Params":
            if self.role not in ("editor", "viewer"):
                raise ValueError("role must be 'editor' or 'viewer'")
            return self

    class Response(BaseModel):
        user_id: str
        role: str
