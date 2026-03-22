"""Add member to recipe book endpoint."""

from pydantic import BaseModel, model_validator
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.services.activity_service import create_activity


class AddRecipeBookMember(Endpoint):
    """Add a member to a recipe book (owner only)."""

    def execute(self, recipe_book_id: str, params: "AddRecipeBookMember.Params"):
        user: User = self.user

        # Only owners can add members
        caller_membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe_book_id,
        )
        if not caller_membership or caller_membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the owner can add members to this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Look up target user
        target_user = self.database.find_by(User, id=params.user_id)
        if not target_user:
            raise APIException(
                status_code=404,
                detail="User not found",
                code=ErrorCode.USER_NOT_FOUND,
            )

        # Check not already a member
        existing = self.database.find_by(
            RecipeBookUser,
            user_id=target_user.id,
            recipe_book_id=recipe_book_id,
        )
        if existing:
            raise APIException(
                status_code=409,
                detail="User is already a member of this recipe book",
                code=ErrorCode.CONFLICT,
            )

        # Create membership
        membership = RecipeBookUser(
            user_id=target_user.id,
            recipe_book_id=recipe_book_id,
            role=params.role,
            invited_by_id=user.id,
        )
        self.database.create(membership)

        # Create activity for the book owner
        book = self.database.find_by(RecipeBook, id=recipe_book_id)
        book_name = book.name if book else "a recipe book"
        create_activity(
            self.db,
            user_id=user.id,
            activity_type="partner_action",
            title=f"{target_user.name} joined {book_name}",
            action_url=f"/recipe-books/{recipe_book_id}/members?role={caller_membership.role}",
        )

        return success(
            data=AddRecipeBookMember.Response(
                user_id=str(target_user.id),
                name=target_user.name,
                role=params.role,
            )
        )

    class Params(BaseModel):
        user_id: str
        role: str

        @model_validator(mode="after")
        def validate_role(self) -> "AddRecipeBookMember.Params":
            if self.role not in ("editor", "viewer"):
                raise ValueError("role must be 'editor' or 'viewer'")
            return self

    class Response(BaseModel):
        user_id: str
        name: str | None = None
        role: str
