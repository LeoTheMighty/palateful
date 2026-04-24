"""Set default recipe book endpoint."""

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class SetDefaultRecipeBook(AsyncEndpoint):
    """Set the user's default recipe book."""

    async def execute(self, params: "SetDefaultRecipeBook.Params"):
        user: User = self.user

        if params.recipe_book_id is None:
            user.default_recipe_book_id = None
            user.previous_recipe_book_id = None
            await self.db.commit()
            await self.db.refresh(user)
            return success(
                data=SetDefaultRecipeBook.Response(
                    default_recipe_book_id=None,
                    previous_recipe_book_id=None,
                )
            )

        recipe_book = await self.database.find_by(
            RecipeBook, id=params.recipe_book_id
        )
        if not recipe_book or recipe_book.archived_at is not None:
            raise APIException(
                status_code=404,
                detail="Recipe book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        # Check user owns or is a member of the book
        membership = (await self.db.execute(
            select(RecipeBookUser)
            .where(
                RecipeBookUser.recipe_book_id == recipe_book.id,
                RecipeBookUser.user_id == user.id,
                RecipeBookUser.archived_at.is_(None),
            )
            .limit(1)
        )).scalars().first()
        is_member = membership is not None

        if not is_member:
            raise APIException(
                status_code=403,
                detail="You do not have access to this recipe book",
                code=ErrorCode.FORBIDDEN,
            )

        # Shift current default to previous
        if user.default_recipe_book_id and str(user.default_recipe_book_id) != str(params.recipe_book_id):
            user.previous_recipe_book_id = user.default_recipe_book_id

        user.default_recipe_book_id = recipe_book.id
        await self.db.commit()
        await self.db.refresh(user)

        return success(
            data=SetDefaultRecipeBook.Response(
                default_recipe_book_id=str(user.default_recipe_book_id) if user.default_recipe_book_id else None,
                previous_recipe_book_id=str(user.previous_recipe_book_id) if user.previous_recipe_book_id else None,
            )
        )

    class Params(BaseModel):
        recipe_book_id: str | None = None

    class Response(BaseModel):
        default_recipe_book_id: str | None = None
        previous_recipe_book_id: str | None = None
