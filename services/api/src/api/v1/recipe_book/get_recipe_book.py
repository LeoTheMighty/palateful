"""Get recipe book endpoint."""

from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import func

from utils.api.endpoint import Endpoint, APIException, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class GetRecipeBook(Endpoint):
    """Get recipe book details by ID."""

    def execute(self, recipe_book_id: str):
        """
        Get recipe book details including recipes.

        Args:
            recipe_book_id: The recipe book's ID

        Returns:
            Recipe book details with recipe list
        """
        user: User = self.user

        # Check access
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe_book_id
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED
            )

        # Get recipe book
        recipe_book = self.database.find_by(RecipeBook, id=recipe_book_id)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail=f"Recipe book with ID '{recipe_book_id}' not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND
            )

        # Get recipes
        recipes = self.database.where(
            Recipe,
            recipe_book_id=recipe_book_id,
            asc='name'
        ).all()

        recipe_items = [
            GetRecipeBook.RecipeItem(
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
            data=GetRecipeBook.Response(
                id=str(recipe_book.id),
                name=recipe_book.name,
                description=recipe_book.description,
                recipe_count=len(recipes),
                recipes=recipe_items,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            )
        )

    class RecipeItem(BaseModel):
        id: str
        name: str
        description: Optional[str] = None
        prep_time: Optional[int] = None
        cook_time: Optional[int] = None
        servings: Optional[int] = None
        image_url: Optional[str] = None
        created_at: datetime

    class Response(BaseModel):
        id: str
        name: str
        description: Optional[str] = None
        recipe_count: int = 0
        recipes: list["GetRecipeBook.RecipeItem"] = []
        created_at: datetime
        updated_at: datetime
