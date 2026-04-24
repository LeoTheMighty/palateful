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
from api.v1.recipe_book.notifications import (
    notify_recipe_added,
    notify_recipe_forked,
    notify_recipe_note_added,
)
from api.v1.recipe_book.websocket import broadcast_event_to_recipe_book
from dependencies import (
    get_async_database,
    get_current_user_async,
    get_database,
)
from fastapi import APIRouter, Depends
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.user import User
from utils.services.async_database import AsyncDatabase
from utils.services.database import Database
from utils.services.notifications_bridge import notify_via_threadpool

recipe_router = APIRouter(tags=["recipes"])


# Recipes under recipe books
@recipe_router.get("/recipe-books/{book_id}/recipes")
async def list_recipes(
    book_id: str,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    vibe: str | None = None,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List recipes in a recipe book."""
    return await ListRecipes.call(
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
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Create a new recipe in a recipe book."""
    result = await CreateRecipe.call(
        book_id=book_id,
        params=params,
        user=user,
        database=database,
    )
    await broadcast_event_to_recipe_book(
        book_id, "recipe_added",
        {"name": params.name},
        user_id=str(user.id),
    )
    # Push notification to other book members (shared books only). The
    # sync `notify_recipe_added` helper still takes `database: Database`
    # so it runs on a fresh sync session inside the threadpool thread.
    book = await database.find_by(RecipeBook, id=book_id)
    if book and book.is_shared:
        await notify_via_threadpool(
            notify_recipe_added,
            recipe_book_id=str(book_id),
            recipe_book_name=book.name or "Shared Recipe Book",
            recipe_name=params.name,
            added_by_user=user,
            image_url=params.image_url,
        )
    return result


# Vibe options (must be before /recipes/{recipe_id} to avoid path collision)
@recipe_router.get("/recipes/vibes/options")
async def get_vibe_options(
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get the list of valid vibes with display names and colors."""
    return await GetVibeOptions.call(database=database)


# Archived recipes (must be before /recipes/{recipe_id} to avoid path collision)
@recipe_router.get("/recipes/archived")
async def list_archived_recipes(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List the current user's archived recipes."""
    return await ListArchivedRecipes.call(
        user=user,
        database=database,
    )


# Bulk recipe operations (must be before /recipes/{recipe_id} to avoid path collision)
@recipe_router.post("/recipes/bulk/move")
async def bulk_move_recipes(
    params: BulkMoveRecipes.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Move multiple recipes to a different book."""
    return await BulkMoveRecipes.call(
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/bulk/archive")
async def bulk_archive_recipes(
    params: BulkArchiveRecipes.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Archive multiple recipes at once."""
    return await BulkArchiveRecipes.call(
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/bulk/tags")
async def bulk_update_tags(
    params: BulkUpdateTags.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Add or remove tags on multiple recipes."""
    return await BulkUpdateTags.call(
        params=params,
        user=user,
        database=database,
    )


# Public recipe by share token (no auth required — must be before /{recipe_id})
@recipe_router.get("/recipes/public/{token}")
async def get_public_recipe_by_token(
    token: str,
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get a recipe by its public share token (no auth required)."""
    return await GetPublicRecipeByToken.call(token=token, database=database)


# Direct recipe access
@recipe_router.get("/recipes/{recipe_id}")
async def get_recipe(
    recipe_id: str,
    debug: bool = False,
    include: str | None = None,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get recipe details. `debug=true` attaches parser artifacts for admins.

    ffm-9a — optional ``?include=`` CSV (values:
    ``ingredients,steps,comments,versions``) trims the response. When
    omitted, today's full shape is returned; unknown values are silently
    dropped; omitted fields are ABSENT from the JSON, not null.
    """
    return await GetRecipe.call(
        recipe_id=recipe_id,
        debug=debug,
        include=include,
        user=user,
        database=database
    )


@recipe_router.put("/recipes/{recipe_id}")
async def update_recipe(
    recipe_id: str,
    params: UpdateRecipe.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Update a recipe."""
    existing = await database.find_by(Recipe, id=recipe_id)
    book_id = str(existing.recipe_book_id) if existing else None
    result = await UpdateRecipe.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
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
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get version history for a recipe."""
    return await GetRecipeVersions.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.get("/recipes/{recipe_id}/versions/{version_id}")
async def get_recipe_version(
    recipe_id: str,
    version_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get the full snapshot for a specific recipe version."""
    return await GetRecipeVersion.call(
        recipe_id=recipe_id,
        version_id=version_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/versions/{version_id}/restore")
async def restore_recipe_version(
    recipe_id: str,
    version_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Restore a recipe to a previous version snapshot."""
    return await RestoreRecipeVersion.call(
        recipe_id=recipe_id,
        version_id=version_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/notes", status_code=201)
async def add_recipe_note(
    recipe_id: str,
    params: AddRecipeNote.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Add a note to a recipe."""
    # `Endpoint.call()` wraps into a CustomJSONResponse; we need the raw
    # {success, data, status} dict here to inspect the created-note id
    # before firing the back-fan notification, so call `run()` and build
    # the response ourselves via `handle_result`.
    endpoint = AddRecipeNote(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )
    result = await endpoint.run()
    # Back-fan: ping the recipe's book owner when a partner notes their
    # recipe in a shared book. Self-notes and solo-book notes are silent.
    if result.get("success") and result.get("data") is not None:
        recipe = await database.find_by(Recipe, id=recipe_id)
        if recipe is not None:  # pragma: no branch — defensive; success path implies recipe exists
            note_data = result["data"]
            note_id = getattr(note_data, "id", None) or ""
            await notify_via_threadpool(
                notify_recipe_note_added,
                recipe=recipe,
                note_id=str(note_id),
                note_body=params.body,
                actor=user,
            )
    return AddRecipeNote.handle_result(result)


@recipe_router.delete("/recipes/{recipe_id}/notes/{note_id}")
async def delete_recipe_note(
    recipe_id: str,
    note_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Delete a recipe note (soft delete)."""
    return await DeleteRecipeNote.call(
        recipe_id=recipe_id,
        note_id=note_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/photo-upload-url")
async def get_recipe_photo_upload_url(
    recipe_id: str,
    params: GetRecipePhotoUploadUrl.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Generate a presigned URL for uploading a recipe photo."""
    return await GetRecipePhotoUploadUrl.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/share", status_code=201)
async def share_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Generate a public share link for a recipe."""
    return await ShareRecipe.call(recipe_id=recipe_id, user=user, database=database)


@recipe_router.delete("/recipes/{recipe_id}/share")
async def revoke_recipe_share(
    recipe_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Revoke the public share link for a recipe."""
    return await RevokeRecipeShare.call(recipe_id=recipe_id, user=user, database=database)


@recipe_router.get("/recipes/{recipe_id}/meals")
async def list_meals_using_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """md-2: List Meals that reference this recipe as a component."""
    return await ListMealsUsingRecipe.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/favorite")
async def toggle_favorite(
    recipe_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Toggle favorite status on a recipe."""
    return await ToggleFavorite.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.get("/favorites")
async def list_favorites(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List the current user's favorite recipes."""
    return await ListFavorites.call(
        user=user,
        database=database,
    )


@recipe_router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Delete (archive) a recipe."""
    existing = await database.find_by(Recipe, id=recipe_id)
    book_id = str(existing.recipe_book_id) if existing else None
    result = await DeleteRecipe.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
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
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Restore an archived recipe."""
    return await RestoreRecipe.call(
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/move")
async def move_recipe(
    recipe_id: str,
    params: MoveRecipe.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Move a recipe to a different book."""
    return await MoveRecipe.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )


@recipe_router.post("/recipes/{recipe_id}/fork", status_code=201)
async def fork_recipe(
    recipe_id: str,
    params: ForkRecipe.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Fork a recipe into a book you own, preserving lineage."""
    # `Endpoint.call()` wraps into a CustomJSONResponse; we need the raw
    # dict here so we can read the forked-recipe id before firing the
    # partner-activity notification. `handle_result` turns the raw dict
    # into the final response shape at the return site.
    endpoint = ForkRecipe(
        recipe_id=recipe_id, params=params, user=user, database=database
    )
    result = await endpoint.run()
    await broadcast_event_to_recipe_book(
        params.destination_book_id, "recipe_added",
        {"forked_from_recipe_id": recipe_id},
        user_id=str(user.id),
    )
    # Notify the source recipe's book owner that their recipe was forked.
    # Self-forks are no-ops inside `notify_recipe_forked`. The sync
    # helper runs on a fresh sync `Database(db=SessionLocal())` inside
    # the threadpool — it re-fetches the source recipe + target book by
    # id so we only need to hand it the ids here.
    if result.get("success") and result.get("data") is not None:
        source_recipe = await database.find_by(Recipe, id=recipe_id)
        target_book = await database.find_by(
            RecipeBook, id=params.destination_book_id
        )
        if source_recipe is not None:  # pragma: no branch — defensive; success path implies source exists
            await notify_via_threadpool(
                notify_recipe_forked,
                source_recipe=source_recipe,
                forked_recipe_id=str(result["data"].id),
                target_book=target_book,
                actor=user,
            )
    return ForkRecipe.handle_result(result)


@recipe_router.post("/recipes/{recipe_id}/copy")
async def copy_recipe(
    recipe_id: str,
    params: CopyRecipe.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Copy a recipe to a different book."""
    return await CopyRecipe.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database,
    )


# Public endpoints (no auth required)
@recipe_router.get("/recipes/{recipe_id}/public")
async def get_public_recipe(
    recipe_id: str,
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get a publicly shared recipe (no auth required)."""
    return await GetPublicRecipe.call(
        recipe_id=recipe_id,
        database=database
    )


@recipe_router.get("/recipe-books/{book_id}/public")
def get_public_recipe_book(
    book_id: str,
    database: Database = Depends(get_database)
):
    """Get a publicly shared recipe book (no auth required)."""
    return GetPublicRecipeBook.call(
        recipe_book_id=book_id,
        database=database
    )
