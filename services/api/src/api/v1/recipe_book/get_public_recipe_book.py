"""Get public recipe book endpoint (no auth required)."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook


class GetPublicRecipeBook(AsyncEndpoint):
    """Get recipe book details by ID if the book is public."""

    async def execute(self, recipe_book_id: str):
        """
        Get recipe book details for a publicly shared book.

        Args:
            recipe_book_id: The recipe book's ID

        Returns:
            Recipe book details with recipe list
        """
        # Get recipe book
        recipe_book = await self.database.find_by(RecipeBook, id=recipe_book_id)
        if not recipe_book or not recipe_book.is_public:
            raise APIException(
                status_code=404,
                detail="Recipe book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND
            )

        # Get recipes
        recipes = await self.database.where(
            Recipe,
            recipe_book_id=recipe_book_id,
            asc='name'
        ).all()

        recipe_items = [
            GetPublicRecipeBook.RecipeItem(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                image_url=recipe.image_url,
                created_at=recipe.created_at
            )
            for recipe in recipes
        ]

        return success(
            data=GetPublicRecipeBook.Response(
                id=str(recipe_book.id),
                name=recipe_book.name,
                description=recipe_book.description,
                is_public=recipe_book.is_public,
                recipe_count=len(recipes),
                recipes=recipe_items,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            )
        )

    class RecipeItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        servings: int | None = None
        image_url: str | None = None
        created_at: datetime

    class Response(BaseModel):
        id: str
        name: str
        description: str | None = None
        is_public: bool
        recipe_count: int = 0
        recipes: list["GetPublicRecipeBook.RecipeItem"] = []
        created_at: datetime
        updated_at: datetime
