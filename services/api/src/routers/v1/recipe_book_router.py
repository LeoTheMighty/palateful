"""Recipe book endpoints router."""

from api.v1.recipe_book import (
    AddRecipeBookMember,
    ArchiveRecipeBook,
    CreateRecipeBook,
    DeleteRecipeBook,
    GetRecipeBook,
    ListArchivedRecipeBooks,
    ListRecipeBooks,
    RemoveRecipeBookMember,
    RestoreRecipeBook,
    UpdateRecipeBook,
    UpdateRecipeBookMemberRole,
    recipe_book_websocket_handler,
)
from api.v1.recipe_book.notifications import notify_book_shared
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, WebSocket
from utils.models.recipe_book import RecipeBook
from utils.models.user import User
from utils.services.database import Database

recipe_book_router = APIRouter(prefix="/recipe-books", tags=["recipe-books"])


@recipe_book_router.get("")
async def list_recipe_books(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
    limit: int = 20,
    offset: int = 0
):
    """List the user's recipe books."""
    return ListRecipeBooks.call(
        limit=limit,
        offset=offset,
        user=user,
        database=database
    )


@recipe_book_router.post("")
async def create_recipe_book(
    params: CreateRecipeBook.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Create a new recipe book."""
    return CreateRecipeBook.call(params, user=user, database=database)


# Archived recipe books (must be before /{recipe_book_id} to avoid path collision)
@recipe_book_router.get("/archived")
async def list_archived_recipe_books(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List the user's archived recipe books."""
    return ListArchivedRecipeBooks.call(
        user=user,
        database=database,
    )


@recipe_book_router.get("/{recipe_book_id}")
async def get_recipe_book(
    recipe_book_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get recipe book details."""
    return GetRecipeBook.call(
        recipe_book_id=recipe_book_id,
        user=user,
        database=database
    )


@recipe_book_router.put("/{recipe_book_id}")
async def update_recipe_book(
    recipe_book_id: str,
    params: UpdateRecipeBook.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Update a recipe book."""
    return UpdateRecipeBook.call(
        recipe_book_id=recipe_book_id,
        params=params,
        user=user,
        database=database
    )


@recipe_book_router.delete("/{recipe_book_id}")
async def delete_recipe_book(
    recipe_book_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Delete a recipe book."""
    return DeleteRecipeBook.call(
        recipe_book_id=recipe_book_id,
        user=user,
        database=database
    )


@recipe_book_router.post("/{recipe_book_id}/archive")
async def archive_recipe_book(
    recipe_book_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Archive a recipe book."""
    return ArchiveRecipeBook.call(
        recipe_book_id=recipe_book_id,
        user=user,
        database=database,
    )


@recipe_book_router.post("/{recipe_book_id}/restore")
async def restore_recipe_book(
    recipe_book_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Restore an archived recipe book."""
    return RestoreRecipeBook.call(
        recipe_book_id=recipe_book_id,
        user=user,
        database=database,
    )


@recipe_book_router.post("/{recipe_book_id}/members")
async def add_recipe_book_member(
    recipe_book_id: str,
    params: AddRecipeBookMember.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Add a member to a recipe book (owner only)."""
    result = AddRecipeBookMember.call(
        recipe_book_id=recipe_book_id,
        params=params,
        user=user,
        database=database,
    )
    # Notify the newly added member
    target_user = database.find_by(User, id=params.user_id)
    book = database.find_by(RecipeBook, id=recipe_book_id)
    if target_user and book:
        notify_book_shared(
            recipe_book_id=str(recipe_book_id),
            recipe_book_name=book.name or "Shared Recipe Book",
            invited_user=target_user,
            invited_by=user,
            database=database,
        )
    return result


@recipe_book_router.patch("/{recipe_book_id}/members/{target_user_id}")
async def update_recipe_book_member_role(
    recipe_book_id: str,
    target_user_id: str,
    params: UpdateRecipeBookMemberRole.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update a member's role in a recipe book (owner only)."""
    return UpdateRecipeBookMemberRole.call(
        recipe_book_id=recipe_book_id,
        target_user_id=target_user_id,
        params=params,
        user=user,
        database=database,
    )


@recipe_book_router.delete("/{recipe_book_id}/members/{target_user_id}")
async def remove_recipe_book_member(
    recipe_book_id: str,
    target_user_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Remove a member from a recipe book (owner only)."""
    return RemoveRecipeBookMember.call(
        recipe_book_id=recipe_book_id,
        target_user_id=target_user_id,
        user=user,
        database=database,
    )


@recipe_book_router.websocket("/ws/{book_id}")
async def recipe_book_websocket(
    websocket: WebSocket,
    book_id: str,
    database: Database = Depends(get_database),
):
    """
    WebSocket endpoint for real-time recipe book sync.

    Connect with: ws://host/v1/recipe-books/ws/{book_id}?token=JWT

    Message types from client:
    - ping: {"type": "ping"}

    Message types from server:
    - connected: Initial confirmation with online users
    - recipe_added: A recipe was added to this book
    - recipe_updated: A recipe in this book was updated
    - recipe_removed: A recipe in this book was archived/deleted
    - pong: Response to ping
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        from utils.services.auth0 import get_auth0_verifier
        verifier = get_auth0_verifier()
        payload = await verifier.verify_token(token)
        user = database.find_by(User, auth0_id=payload.get("sub"))
        if not user:
            await websocket.close(code=4001, reason="Invalid user")
            return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await recipe_book_websocket_handler(
        websocket=websocket,
        book_id=book_id,
        user=user,
        db=database.db,
    )
