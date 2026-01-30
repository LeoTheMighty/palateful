"""List recipe books endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func
from utils.api.endpoint import Endpoint, success
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListRecipeBooks(Endpoint):
    """List user's recipe books."""

    def execute(self, limit: int = 20, offset: int = 0):
        """
        List all recipe books the user has access to.

        Args:
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Paginated list of recipe books
        """
        user: User = self.user

        # Query recipe books with recipe count
        query = (
            self.db.query(
                RecipeBook,
                func.count(Recipe.id).label('recipe_count')
            )
            .join(RecipeBookUser, RecipeBook.id == RecipeBookUser.recipe_book_id)
            .outerjoin(Recipe, RecipeBook.id == Recipe.recipe_book_id)
            .filter(RecipeBookUser.user_id == user.id)
            .group_by(RecipeBook.id)
            .order_by(RecipeBook.updated_at.desc())
        )

        # Get total count
        total = query.count()

        # Apply pagination
        results = query.offset(offset).limit(limit).all()

        items = [
            ListRecipeBooks.RecipeBookItem(
                id=str(recipe_book.id),
                name=recipe_book.name,
                description=recipe_book.description,
                recipe_count=recipe_count,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at
            )
            for recipe_book, recipe_count in results
        ]

        return success(
            data=ListRecipeBooks.Response(
                items=items,
                total=total,
                limit=limit,
                offset=offset
            )
        )

    class RecipeBookItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        recipe_count: int = 0
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        items: list["ListRecipeBooks.RecipeBookItem"]
        total: int
        limit: int
        offset: int
