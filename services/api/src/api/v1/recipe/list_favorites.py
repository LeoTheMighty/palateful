"""List favorite recipes endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.recipe import Recipe
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


class ListFavorites(Endpoint):
    """List the current user's favorite recipes."""

    def execute(self):
        """
        List all recipes the current user has favorited.

        Returns:
            List of favorite recipes ordered by most recently favorited.
        """
        user: User = self.user

        # Query favorites joined with recipes, ordered newest first
        results = (
            self.db.query(UserFavorite, Recipe)
            .join(Recipe, UserFavorite.recipe_id == Recipe.id)
            .filter(UserFavorite.user_id == user.id)
            .filter(Recipe.archived_at.is_(None))
            .order_by(UserFavorite.created_at.desc())
            .all()
        )

        items = [
            ListFavorites.FavoriteItem(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                image_url=recipe.image_url,
                tags=recipe.tags or [],
                is_favorite=True,
                created_at=recipe.created_at,
            )
            for _fav, recipe in results
        ]

        return success(
            data=ListFavorites.Response(
                items=items,
                total=len(items),
            )
        )

    class FavoriteItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        servings: int | None = None
        image_url: str | None = None
        tags: list[str] = []
        is_favorite: bool = True
        created_at: datetime

    class Response(BaseModel):
        items: list["ListFavorites.FavoriteItem"]
        total: int
