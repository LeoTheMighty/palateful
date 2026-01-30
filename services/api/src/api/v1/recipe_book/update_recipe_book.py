"""Update recipe book endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class UpdateRecipeBook(Endpoint):
    """Update a recipe book."""

    def execute(self, recipe_book_id: str, params: "UpdateRecipeBook.Params"):
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
        membership = self.database.find_by(
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
        recipe_book = self.database.find_by(RecipeBook, id=recipe_book_id)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail=f"Recipe book with ID '{recipe_book_id}' not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND
            )

        # Build update dict
        updates = {}
        if params.name is not None:
            updates["name"] = params.name
        if params.description is not None:
            updates["description"] = params.description

        # Update if there are changes
        if updates:
            self.database.update(recipe_book, **updates)

        # Get recipe count
        recipe_count = self.db.query(func.count(Recipe.id)).filter(
            Recipe.recipe_book_id == recipe_book_id
        ).scalar() or 0

        return success(
            data=UpdateRecipeBook.Response(
                id=recipe_book.id,
                name=recipe_book.name,
                description=recipe_book.description,
                recipe_count=recipe_count,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            )
        )

    class Params(BaseModel):
        name: str | None = None
        description: str | None = None

    class Response(BaseModel):
        id: str
        name: str
        description: str | None = None
        recipe_count: int
        created_at: datetime
        updated_at: datetime
