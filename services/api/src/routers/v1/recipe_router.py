"""Recipe endpoints router."""


from api.v1.recipe import (
    CreateRecipe,
    DeleteRecipe,
    GetRecipe,
    ListRecipes,
    UpdateRecipe,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
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
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List recipes in a recipe book."""
    return ListRecipes.call(
        book_id=book_id,
        limit=limit,
        offset=offset,
        search=search,
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
    return CreateRecipe.call(
        book_id=book_id,
        params=params,
        user=user,
        database=database
    )


# Direct recipe access
@recipe_router.get("/recipes/{recipe_id}")
async def get_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Get recipe details."""
    return GetRecipe.call(
        recipe_id=recipe_id,
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
    return UpdateRecipe.call(
        recipe_id=recipe_id,
        params=params,
        user=user,
        database=database
    )


@recipe_router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database)
):
    """Delete a recipe."""
    return DeleteRecipe.call(
        recipe_id=recipe_id,
        user=user,
        database=database
    )
