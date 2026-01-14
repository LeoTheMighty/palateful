"""Ingredient endpoints router."""

from fastapi import APIRouter, Depends

from dependencies import get_database, get_current_user
from utils.models.user import User
from utils.services.database import Database
from api.v1.ingredient import SearchIngredients, CreateIngredient, GetIngredient


ingredient_router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@ingredient_router.get("/search")
async def search_ingredients(
    q: str,
    limit: int = 10,
    database: Database = Depends(get_database)
):
    """
    Search for ingredients using fuzzy matching.

    No authentication required.
    """
    # Get database manually since this endpoint doesn't require auth
    return SearchIngredients.call(q=q, limit=limit, database=database)


@ingredient_router.post("")
async def create_ingredient(
    params: CreateIngredient.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Create a new ingredient."""
    return CreateIngredient.call(params, user=user, database=database)


@ingredient_router.get("/{ingredient_id}")
async def get_ingredient(
    ingredient_id: str,
    database: Database = Depends(get_database)
):
    """Get ingredient details by ID."""
    return GetIngredient.call(ingredient_id=ingredient_id, database=database)
