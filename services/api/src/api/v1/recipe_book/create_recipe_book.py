"""Create recipe book endpoint."""

from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from utils.api.endpoint import Endpoint, success
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class CreateRecipeBook(Endpoint):
    """Create a new recipe book."""

    def execute(self, params: "CreateRecipeBook.Params"):
        """
        Create a new recipe book for the current user.

        Args:
            params: Recipe book creation parameters

        Returns:
            Created recipe book data
        """
        user: User = self.user

        # Create recipe book
        recipe_book = RecipeBook(
            name=params.name,
            description=params.description
        )
        self.database.create(recipe_book)
        self.database.db.refresh(recipe_book)

        # Create ownership relationship
        membership = RecipeBookUser(
            user_id=user.id,
            recipe_book_id=recipe_book.id,
            role="owner"
        )
        self.database.create(membership)
        self.database.db.refresh(membership)

        return success(
            data=CreateRecipeBook.Response(
                id=recipe_book.id,
                name=recipe_book.name,
                description=recipe_book.description,
                recipe_count=0,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            ),
            status=201
        )

    class Params(BaseModel):
        name: str
        description: Optional[str] = None

    class Response(BaseModel):
        id: str
        name: str
        description: Optional[str] = None
        recipe_count: int
        created_at: datetime
        updated_at: datetime
