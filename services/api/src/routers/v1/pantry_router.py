"""Pantry endpoints router.

aam-15: router flipped to `get_async_database` + `get_current_user_async`.
Every endpoint dispatches through `await Foo.call(...)` on an
`AsyncEndpoint` subclass. The sync `pantry_service.py` helpers stay
because shopping_list (aam-13) + `pantry_meal_subscriber` are still
sync; aam-15 added `*_async` twins for the AsyncEndpoint call paths.
"""

from api.v1.pantry import (
    AddPantryIngredient,
    DeletePantryIngredient,
    EstimateExpiry,
    GetDefaultPantry,
    UpdatePantryIngredient,
)
from api.v1.pantry.schemas import PantryIngredientCreate, PantryIngredientUpdate
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

pantry_router = APIRouter(tags=["pantries"])


@pantry_router.get("/pantries/default")
async def get_default_pantry(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Return the caller's default pantry (lazy-creating it if needed)."""
    return await GetDefaultPantry.call(user=user, database=database)


@pantry_router.post("/pantries/{pantry_id}/ingredients")
async def add_pantry_ingredient(
    pantry_id: str,
    params: PantryIngredientCreate,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Insert or upsert-by-quantity a pantry ingredient."""
    return await AddPantryIngredient.call(
        pantry_id=pantry_id,
        params=params,
        user=user,
        database=database,
    )


@pantry_router.patch("/pantries/{pantry_id}/ingredients/{ingredient_id}")
async def update_pantry_ingredient(
    pantry_id: str,
    ingredient_id: str,
    params: PantryIngredientUpdate,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Partially update a pantry ingredient."""
    return await UpdatePantryIngredient.call(
        pantry_id=pantry_id,
        ingredient_id=ingredient_id,
        params=params,
        user=user,
        database=database,
    )


@pantry_router.post("/pantries/{pantry_id}/estimate-expiry")
async def estimate_pantry_expiry(
    pantry_id: str,
    params: EstimateExpiry.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Return an expires_at estimate for (ingredient, storage_location)."""
    return await EstimateExpiry.call(
        pantry_id=pantry_id,
        params=params,
        user=user,
        database=database,
    )


@pantry_router.delete("/pantries/{pantry_id}/ingredients/{ingredient_id}")
async def delete_pantry_ingredient(
    pantry_id: str,
    ingredient_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Soft-delete a pantry ingredient (idempotent)."""
    return await DeletePantryIngredient.call(
        pantry_id=pantry_id,
        ingredient_id=ingredient_id,
        user=user,
        database=database,
    )
