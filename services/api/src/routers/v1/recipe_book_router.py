"""Recipe book endpoints router."""

from api.v1.recipe_book import (
    CreateRecipeBook,
    DeleteRecipeBook,
    GetRecipeBook,
    ListRecipeBooks,
    UpdateRecipeBook,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
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
