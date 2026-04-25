"""Bulk move recipes to another book endpoint."""

from pydantic import BaseModel, Field
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class BulkMoveRecipes(AsyncEndpoint):
    """Move multiple recipes to a different recipe book.

    Returns the list of moved recipes with their **prior** book id so
    the caller can build a one-tap Undo affordance without re-fetching
    each recipe (recipe-bulk-org-2). Recipes that were already in the
    destination are skipped silently and do not appear in `moved`.
    """

    async def execute(self, params: "BulkMoveRecipes.Params"):
        user: User = self.user

        if not params.recipe_ids:
            raise APIException(
                status_code=400,
                detail="No recipes specified",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Validate destination book exists and user has editor/owner access
        dest_book = await self.database.find_by(RecipeBook, id=params.destination_book_id)
        if not dest_book:
            raise APIException(
                status_code=404,
                detail="Destination book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )
        dest_membership = await self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=params.destination_book_id,
        )
        if not dest_membership or dest_membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to add recipes to this book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Load and validate all recipes; capture prior_recipe_book_id
        # for each recipe that will actually move.
        moved_recipes: list[tuple[Recipe, str]] = []
        for recipe_id in params.recipe_ids:
            recipe = await self.database.find_by(Recipe, id=recipe_id)
            if not recipe:
                raise APIException(
                    status_code=404,
                    detail=f"Recipe not found: {recipe_id}",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )
            # Skip recipes already in destination (idempotent)
            if str(recipe.recipe_book_id) == params.destination_book_id:
                continue
            src_membership = await self.database.find_by(
                RecipeBookUser,
                user_id=str(user.id),
                recipe_book_id=recipe.recipe_book_id,
            )
            if not src_membership or src_membership.role not in ("owner", "editor"):
                raise APIException(
                    status_code=403,
                    detail="You don't have permission to move this recipe",
                    code=ErrorCode.RECIPE_ACCESS_DENIED,
                )
            moved_recipes.append((recipe, str(recipe.recipe_book_id)))

        # Perform moves
        for recipe, _prior in moved_recipes:
            recipe.recipe_book_id = params.destination_book_id
        await self.database.db.commit()

        return success(
            data=BulkMoveRecipes.Response(
                moved=[
                    BulkMoveRecipes.MovedItem(
                        id=str(recipe.id),
                        prior_recipe_book_id=prior,
                    )
                    for recipe, prior in moved_recipes
                ],
                moved_count=len(moved_recipes),
            )
        )

    class Params(BaseModel):
        recipe_ids: list[str] = Field(max_length=100)
        destination_book_id: str

    class MovedItem(BaseModel):
        id: str
        prior_recipe_book_id: str

    class Response(BaseModel):
        moved: list["BulkMoveRecipes.MovedItem"] = Field(default_factory=list)
        moved_count: int
