"""Add a note to a recipe."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_note import RecipeNote
from utils.models.user import User


class AddRecipeNote(Endpoint):
    """Add a note to a recipe.

    Any user with at least read access (viewer, editor, owner) can add notes.
    """

    class Params(BaseModel):
        body: str

    def execute(self, recipe_id: str, params: "AddRecipeNote.Params"):
        user: User = self.user

        # Get recipe
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Check access — any member (viewer, editor, owner) may add notes
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id,
        )
        if not membership:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        note = RecipeNote(
            recipe_id=recipe_id,
            body=params.body,
            created_by=user.id,
        )
        self.database.create(note)

        return success(
            status=201,
            data=AddRecipeNote.Response(
                id=str(note.id),
                recipe_id=str(note.recipe_id),
                body=note.body,
                created_by=str(note.created_by) if note.created_by else None,
                created_at=note.created_at,
            ),
        )

    class Response(BaseModel):
        id: str
        recipe_id: str
        body: str
        created_by: str | None = None
        created_at: datetime
