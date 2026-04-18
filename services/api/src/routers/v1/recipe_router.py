"""Recipe endpoints router."""


from api.v1.recipe import (
    AddRecipeNote,
    BulkArchiveRecipes,
    BulkMoveRecipes,
    BulkUpdateTags,
    CopyRecipe,
    CreateRecipe,
    DeleteRecipe,
    DeleteRecipeNote,
    ForkRecipe,
    GetPublicRecipe,
    GetPublicRecipeByToken,
    GetRecipe,
    GetRecipePhotoUploadUrl,
    GetRecipeVersion,
    GetRecipeVersions,
    GetVibeOptions,
    ListArchivedRecipes,
    ListFavorites,
    ListMealsUsingRecipe,
    ListRecipes,
    MoveRecipe,
    RestoreRecipe,
    RestoreRecipeVersion,
    RevokeRecipeShare,
    ShareRecipe,
    ToggleFavorite,
    UpdateRecipe,
)
from api.v1.recipe_book import GetPublicRecipeBook
from api.v1.recipe_book.notifications import notify_recipe_added
from api.v1.recipe_book.websocket import broadcast_event_to_recipe_book
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.user import User
from utils.services.database import Database

recipe_router = APIRouter(tags=["recipes"])


# Recipes under recipe books
@recipe_router.get("/recipe-books/{book_id}/recipes")
async def list_recipes(
    book_id: str,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    vibe: str | None = None,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List recipes in a recipe book."""
    return ListRecipes.call(
        book_id=book_id,
        limit=limit,
        offset=offset,
        search=search,
        vibe=vibe,
        user=user,
        database=database
    )


@recipe_router.post("/recipe-books/{book_id}/recipes")
async def create_recipe(
    book_id: str,
    params: CreateRecipe.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Create a new recipe in a recipe book."""
    result = CreateRecipe.call(
        book_id=book_id,
        params=params,
        user=user,
        database=database
    )
    await broadcast_event_to_recipe_book(
        book_id, "recipe_added",
        {"name": params.name},
        user_id=str(user.id),
    )
    # Push notification to other book members (shared books only)
    book = database.find_by(RecipeBook, id=book_id)
    if book and book.is_shared:
        notify_recipe_added(
            recipe_book_id=str(book_id),
            recipe_book_name=book.name or "Shared Recipe Book",
            recipe_name=params.name,
            added_by_user=user,
            database=database,
        )
    return result


# Vibe options (must be before /recipes/{recipe_id} to avoid path collision)
@recipe_router.get("/recipes/vibes/options")
async def get_vibe_options(
    database: Database = Depends(get_database),
):
    """Get the list of valid vibes with display names and colors."""
    return GetVibeOptions.call(database=database)


# Archived recipes (must be before /recipes/{recipe_id} to avoid path collision)
@recipe_router.get("/recipes/archived")
async def list_archived_recipes(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List the current user's archived recipes."""
    return ListArchivedRecipes.call(
        user=user,
        database=database,
    )


# Bulk recipe operations (must be before /recipes/{recipe_id} to avoid path collision)
@recipe_router.post("/recipes/bulk/move")
async def bulk_move_recipes(
    params: BulkMoveRecipes.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Move multiple recipes to a different book."""
    return BulkMoveRecipes.call(
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/bulk/archive")
async def bulk_archive_recipes(
    params: BulkArchiveRecipes.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Archive multiple recipes at once."""
    return BulkArchiveRecipes.call(
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/bulk/tags")
async def bulk_update_tags(
    params: BulkUpdateTags.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Add or remove tags on multiple recipes."""
    return BulkUpdateTags.call(
        params=params,
        user=user,
        database=database,
    )


# Public recipe by share token (no auth required — must be before /{recipe_id})
@recipe_router.get("/recipes/public/{token}")
async def get_public_recipe_by_token(
    token: str,
    database: Database = Depends(get_database),
):
    """Get a recipe by its public share token (no auth required)."""
    return GetPublicRecipeByToken.call(token=token, database=database)


# Direct recipe access
@recipe_router.get("/recipes/{recipe_id}")
async def get_recipe(
    recipe_id: str,
    debug: bool = False,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get recipe details. `debug=true` attaches parser artifacts for admins."""
    return GetRecipe.call(
        recipe_id=recipe_id,
        debug=debug,
        user=user,
        database=database
    )


@recipe_router.put("/recipes/{recipe_id}")
async def update_recipe(
    recipe_id: str,
    params: UpdateRecipe.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Update a recipe."""
    existing = database.find_by(Recipe, id=recipe_id)
    book_id = str(existing.recipe_book_id) if existing else None
    result = UpdateRecipe.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database
    )
    if book_id:
        await broadcast_event_to_recipe_book(
            book_id, "recipe_updated",
            {"recipe_id": recipe_id},
            user_id=str(user.id),
        )
    return result


@recipe_router.get("/recipes/{recipe_id}/versions")
async def get_recipe_versions(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get version history for a recipe."""
    return GetRecipeVersions.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.get("/recipes/{recipe_id}/versions/{version_id}")
async def get_recipe_version(
    recipe_id: str,
    version_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get the full snapshot for a specific recipe version."""
    return GetRecipeVersion.call(
        recipe_id=recipe_id,
        version_id=version_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/versions/{version_id}/restore")
async def restore_recipe_version(
    recipe_id: str,
    version_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Restore a recipe to a previous version snapshot."""
    return RestoreRecipeVersion.call(
        recipe_id=recipe_id,
        version_id=version_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/notes", status_code=201)
async def add_recipe_note(
    recipe_id: str,
    params: AddRecipeNote.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Add a note to a recipe."""
    return AddRecipeNote.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )


@recipe_router.delete("/recipes/{recipe_id}/notes/{note_id}")
async def delete_recipe_note(
    recipe_id: str,
    note_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Delete a recipe note (soft delete)."""
    return DeleteRecipeNote.call(
        recipe_id=recipe_id,
        note_id=note_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/photo-upload-url")
async def get_recipe_photo_upload_url(
    recipe_id: str,
    params: GetRecipePhotoUploadUrl.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Generate a presigned URL for uploading a recipe photo."""
    return GetRecipePhotoUploadUrl.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/share", status_code=201)
async def share_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Generate a public share link for a recipe."""
    return ShareRecipe.call(recipe_id=recipe_id, user=user, database=database)


@recipe_router.delete("/recipes/{recipe_id}/share")
async def revoke_recipe_share(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Revoke the public share link for a recipe."""
    return RevokeRecipeShare.call(recipe_id=recipe_id, user=user, database=database)


@recipe_router.get("/recipes/{recipe_id}/meals")
async def list_meals_using_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """md-2: List Meals that reference this recipe as a component."""
    return ListMealsUsingRecipe.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/favorite")
async def toggle_favorite(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Toggle favorite status on a recipe."""
    return ToggleFavorite.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.get("/favorites")
async def list_favorites(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List the current user's favorite recipes."""
    return ListFavorites.call(
        user=user,
        database=database,
    )


@recipe_router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Delete (archive) a recipe."""
    existing = database.find_by(Recipe, id=recipe_id)
    book_id = str(existing.recipe_book_id) if existing else None
    result = DeleteRecipe.call(
        recipe_id=recipe_id,
        user=user,
        database=database
    )
    if book_id:
        await broadcast_event_to_recipe_book(
            book_id, "recipe_removed",
            {"recipe_id": recipe_id},
            user_id=str(user.id),
        )
    return result


@recipe_router.post("/recipes/{recipe_id}/restore")
async def restore_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Restore an archived recipe."""
    return RestoreRecipe.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/move")
async def move_recipe(
    recipe_id: str,
    params: MoveRecipe.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Move a recipe to a different book."""
    return MoveRecipe.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/fork", status_code=201)
async def fork_recipe(
    recipe_id: str,
    params: ForkRecipe.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Fork a recipe into a book you own, preserving lineage."""
    result = ForkRecipe.call(recipe_id=recipe_id, params=params, user=user, database=database)
    await broadcast_event_to_recipe_book(
        params.destination_book_id, "recipe_added",
        {"forked_from_recipe_id": recipe_id},
        user_id=str(user.id),
    )
    return result


@recipe_router.post("/recipes/{recipe_id}/copy")
async def copy_recipe(
    recipe_id: str,
    params: CopyRecipe.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Copy a recipe to a different book."""
    return CopyRecipe.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )


# Public endpoints (no auth required)
@recipe_router.get("/recipes/{recipe_id}/public")
async def get_public_recipe(
    recipe_id: str,
    database: Database = Depends(get_database)
):
    """Get a publicly shared recipe (no auth required)."""
    return GetPublicRecipe.call(
        recipe_id=recipe_id,
        database=database
    )


@recipe_router.get("/recipe-books/{book_id}/public")
async def get_public_recipe_book(
    book_id: str,
    database: Database = Depends(get_database)
):
    """Get a publicly shared recipe book (no auth required)."""
    return GetPublicRecipeBook.call(
        recipe_book_id=book_id,
        database=database
    )
