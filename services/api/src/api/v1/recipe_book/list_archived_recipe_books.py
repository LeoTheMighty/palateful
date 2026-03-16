"""List archived recipe books endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func
from utils.api.endpoint import Endpoint, success
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListArchivedRecipeBooks(Endpoint):
    """List the current user's archived recipe books."""

    def execute(self):
        user: User = self.user

        # Query archived recipe books with recipe count
        results = (
            self.db.query(
                RecipeBook,
                func.count(Recipe.id).label("recipe_count"),
            )
            .join(RecipeBookUser, RecipeBook.id == RecipeBookUser.recipe_book_id)
            .outerjoin(
                Recipe,
                (RecipeBook.id == Recipe.recipe_book_id)
                & (Recipe.archived_at.is_(None)),
            )
            .filter(
                RecipeBookUser.user_id == user.id,
                RecipeBook.archived_at.isnot(None),
            )
            .group_by(RecipeBook.id)
            .order_by(RecipeBook.archived_at.desc())
            .all()
        )

        items = [
            ListArchivedRecipeBooks.ArchivedBookItem(
                id=str(book.id),
                name=book.name,
                description=book.description,
                recipe_count=recipe_count,
                archived_at=book.archived_at,
                created_at=book.created_at,
            )
            for book, recipe_count in results
        ]

        return success(
            data=ListArchivedRecipeBooks.Response(
                items=items,
                total=len(items),
            )
        )

    class ArchivedBookItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        recipe_count: int = 0
        archived_at: datetime
        created_at: datetime

    class Response(BaseModel):
        items: list["ListArchivedRecipeBooks.ArchivedBookItem"]
        total: int
