"""Meal endpoints router.

Endpoints split across two mount points:
  * `/v1/meals/*` — standalone Meal operations.
  * `/v1/recipe-books/{book_id}/meals` — book-scoped list + create.

The book-scoped routes ship under a second APIRouter at the
`/recipe-books` prefix (same approach as `recipe_router.py`, which
carries both `/recipes` and `/recipe-books/{id}/recipes/...`).
"""

from api.v1.meal import (
    AddRecipeToMeal,
    ArchiveMeal,
    CreateMeal,
    FavoriteMeal,
    GetMeal,
    GetPublicMealByToken,
    ListMeals,
    ListMealsInBook,
    RemoveRecipeFromMeal,
    ReorderMealComponents,
    RestoreMeal,
    ShareMeal,
    UnfavoriteMeal,
    UpdateMeal,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from schemas.meal import (
    MealComponentAddRequest,
    MealCreateRequest,
    MealReorderRequest,
    MealUpdateRequest,
)
from utils.models.user import User
from utils.services.database import Database

meal_router = APIRouter(prefix="/meals", tags=["meals"])
book_meal_router = APIRouter(prefix="/recipe-books", tags=["meals"])


# ---------- /v1/meals ----------


@meal_router.get("")
async def list_meals(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
    limit: int | None = None,
    offset: int = 0,
    include_archived: bool = False,
    archived: bool | None = None,
    scope: str | None = None,
):
    """List Meals across every readable book.

    md-3 filter knobs: `archived=true` returns only archived (archive
    view); `scope=home` raises the default limit to 30 and pins the sort
    to `updated_at DESC` for the home grid.
    """
    return ListMeals.call(
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        archived=archived,
        scope=scope,
        user=user,
        database=database,
    )


# Public Meal by share token (no auth — MUST be registered BEFORE any
# `/{meal_id}` path-param route so FastAPI matches `public` literally
# instead of treating it as a meal_id. Mirrors the pattern in
# `recipe_router.py` line 165.)
@meal_router.get("/public/{token}")
async def get_public_meal_by_token(
    token: str,
    database: Database = Depends(get_database),
):
    """Get a Meal by its public share token (no auth required)."""
    return GetPublicMealByToken.call(token=token, database=database)


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
    dedicated add/remove/reorder endpoints."""
    return UpdateMeal.call(
        meal_id=meal_id, params=params, user=user, database=database
    )


@meal_router.post("/{meal_id}/recipes")
async def add_recipe_to_meal(
    meal_id: str,
    params: MealComponentAddRequest,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Attach an additional component recipe to a Meal."""
    return AddRecipeToMeal.call(
        meal_id=meal_id, params=params, user=user, database=database
    )


@meal_router.delete("/{meal_id}/recipes/{recipe_id}")
async def remove_recipe_from_meal(
    meal_id: str,
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Detach a component from a Meal (rejects if it would leave <2)."""
    return RemoveRecipeFromMeal.call(
        meal_id=meal_id,
        recipe_id=recipe_id,
        user=user,
        database=database,
    )


@meal_router.post("/{meal_id}/reorder")
async def reorder_meal_components(
    meal_id: str,
    params: MealReorderRequest,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Atomically rewrite order_index for every component."""
    return ReorderMealComponents.call(
        meal_id=meal_id, params=params, user=user, database=database
    )


@meal_router.post("/{meal_id}/favorite")
async def favorite_meal(
    meal_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Pin a Meal to the user's favorites (idempotent)."""
    return FavoriteMeal.call(meal_id=meal_id, user=user, database=database)


@meal_router.delete("/{meal_id}/favorite")
async def unfavorite_meal(
    meal_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Remove a Meal from favorites (idempotent)."""
    return UnfavoriteMeal.call(
        meal_id=meal_id, user=user, database=database
    )


@meal_router.post("/{meal_id}/share")
async def share_meal(
    meal_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Generate (or return) a Meal's public share token.

    Idempotent — re-POSTing returns the same token with a 200 instead of
    rotating it. Matches the ShareRecipe contract.
    """
    return ShareMeal.call(meal_id=meal_id, user=user, database=database)


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
