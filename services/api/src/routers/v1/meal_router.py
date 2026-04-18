"""Meal endpoints router.

Endpoints split across two mount points:
  * `/v1/meals/*` — standalone Meal operations.
  * `/v1/recipe-books/{book_id}/meals` — book-scoped list + create.

The book-scoped routes ship under a second APIRouter at the
`/recipe-books` prefix (same approach as `recipe_router.py`, which
carries both `/recipes` and `/recipe-books/{id}/recipes/...`).
"""

from api.v1.meal import (
    ArchiveMeal,
    CreateMeal,
    GetMeal,
    ListMeals,
    ListMealsInBook,
    RestoreMeal,
    UpdateMeal,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from schemas.meal import MealCreateRequest, MealUpdateRequest
from utils.models.user import User
from utils.services.database import Database

meal_router = APIRouter(prefix="/meals", tags=["meals"])
book_meal_router = APIRouter(prefix="/recipe-books", tags=["meals"])


# ---------- /v1/meals ----------


@meal_router.get("")
async def list_meals(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
):
    """List Meals across every readable book."""
    return ListMeals.call(
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        user=user,
        database=database,
    )


@meal_router.get("/{meal_id}")
async def get_meal(
    meal_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get a Meal by id — requires read membership on its book."""
    return GetMeal.call(meal_id=meal_id, user=user, database=database)


@meal_router.patch("/{meal_id}")
async def update_meal(
    meal_id: str,
    params: MealUpdateRequest,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update name / description. Component edits go through the
    dedicated add/remove/reorder endpoints (mcv-3)."""
    return UpdateMeal.call(
        meal_id=meal_id, params=params, user=user, database=database
    )


@meal_router.post("/{meal_id}/archive")
async def archive_meal(
    meal_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Soft-archive a Meal."""
    return ArchiveMeal.call(meal_id=meal_id, user=user, database=database)


@meal_router.post("/{meal_id}/restore")
async def restore_meal(
    meal_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Un-archive a Meal."""
    return RestoreMeal.call(meal_id=meal_id, user=user, database=database)


# ---------- /v1/recipe-books/{book_id}/meals ----------


@book_meal_router.get("/{book_id}/meals")
async def list_meals_in_book(
    book_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
):
    """List Meals in a specific recipe_book."""
    return ListMealsInBook.call(
        book_id=book_id,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        user=user,
        database=database,
    )


@book_meal_router.post("/{book_id}/meals")
async def create_meal(
    book_id: str,
    params: MealCreateRequest,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a Meal inside this book."""
    return CreateMeal.call(
        book_id=book_id, params=params, user=user, database=database
    )
