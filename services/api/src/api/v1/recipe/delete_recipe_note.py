"""Delete (soft-delete) a recipe note."""

from datetime import UTC, datetime

from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_note import RecipeNote
from utils.models.user import User


class DeleteRecipeNote(AsyncEndpoint):
    """Soft-delete a recipe note.

    The note creator or the recipe book owner may delete a note.
    Deletion sets archived_at — the note is never hard-deleted.
    """

    async def execute(self, recipe_id: str, note_id: str):
        user: User = self.user

        # Get recipe
        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Check membership
        membership = await self.database.find_by(
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

        # Get note (exclude archived)
        note = await self.database.find_by(RecipeNote, id=note_id)
        if not note or str(note.recipe_id) != str(recipe_id) or note.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Note with ID '{note_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )

        # Authorization: note creator or book owner
        is_note_creator = note.created_by is not None and str(note.created_by) == str(user.id)
        is_book_owner = membership.role == "owner"
        if not is_note_creator and not is_book_owner:
            raise APIException(
                status_code=403,
                detail="You don't have permission to delete this note",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        await self.database.update(note, archived_at=datetime.now(UTC))

        return success(data={"deleted": True})
