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

        # Subquery: total member count per book
        member_count_subq = (
            self.db.query(
                RecipeBookUser.recipe_book_id,
                func.count(RecipeBookUser.user_id).label("member_count"),
            )
            .filter(RecipeBookUser.archived_at.is_(None))
            .group_by(RecipeBookUser.recipe_book_id)
            .subquery()
        )

        # Main query: recipe books with recipe count, user role, and member count
        query = (
            self.db.query(
                RecipeBook,
                func.count(Recipe.id).label("recipe_count"),
                RecipeBookUser.role.label("user_role"),
                func.coalesce(member_count_subq.c.member_count, 1).label("member_count"),
                RecipeBookUser.last_opened_at.label("last_opened_at"),
            )
            .join(
                RecipeBookUser,
                (RecipeBook.id == RecipeBookUser.recipe_book_id)
                & (RecipeBookUser.user_id == user.id),
            )
            .outerjoin(
                Recipe,
                (RecipeBook.id == Recipe.recipe_book_id) & (Recipe.archived_at.is_(None)),
            )
            .outerjoin(member_count_subq, RecipeBook.id == member_count_subq.c.recipe_book_id)
            .filter(RecipeBook.archived_at.is_(None))
            .group_by(RecipeBook.id, RecipeBookUser.role, RecipeBookUser.last_opened_at, member_count_subq.c.member_count)
            .order_by(RecipeBookUser.last_opened_at.desc().nullslast())
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
                is_public=recipe_book.is_public,
                is_shared=recipe_book.is_shared,
                user_role=user_role,
                recipe_count=recipe_count,
                member_count=member_count,
                last_opened_at=last_opened_at,
                created_at=recipe_book.created_at,
                updated_at=recipe_book.updated_at,
            )
            for recipe_book, recipe_count, user_role, member_count, last_opened_at in results
        ]

        return success(
            data=ListRecipeBooks.Response(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
            )
        )

    class RecipeBookItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        is_public: bool = False
        is_shared: bool = False
        user_role: str = "owner"
        recipe_count: int = 0
        member_count: int = 1
        last_opened_at: datetime | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        items: list["ListRecipeBooks.RecipeBookItem"]
        total: int
        limit: int
        offset: int
