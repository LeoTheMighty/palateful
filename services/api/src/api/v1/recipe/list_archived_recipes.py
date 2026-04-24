"""List archived recipes endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListArchivedRecipes(AsyncEndpoint):
    """List the current user's archived recipes."""

    async def execute(self):
        """
        List all archived recipes across books the user has access to.

        Returns:
            List of archived recipes ordered by most recently archived.
        """
        user: User = self.user

        # Get all recipe book IDs the user has membership in
        memberships = await self.database.where(
            RecipeBookUser, user_id=str(user.id)
        ).all()
        book_ids = [m.recipe_book_id for m in memberships]

        if not book_ids:
            return success(data=ListArchivedRecipes.Response(items=[], total=0))

        # Query archived recipes across those books
        list_result = await self.database.db.execute(
            select(Recipe)
            .where(
                Recipe.recipe_book_id.in_(book_ids),
                Recipe.archived_at.isnot(None),
            )
            .order_by(Recipe.archived_at.desc())
        )
        results = list(list_result.scalars().all())

        items = [
            ListArchivedRecipes.ArchivedRecipeItem(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                servings=recipe.servings,
                image_url=recipe.image_url,
                tags=recipe.tags or [],
                archived_at=recipe.archived_at,
                created_at=recipe.created_at,
            )
            for recipe in results
        ]

        return success(
            data=ListArchivedRecipes.Response(
                items=items,
                total=len(items),
            )
        )

    class ArchivedRecipeItem(BaseModel):
        id: str
        name: str
        description: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        servings: int | None = None
        image_url: str | None = None
        tags: list[str] = []
        archived_at: datetime
        created_at: datetime

    class Response(BaseModel):
        items: list["ListArchivedRecipes.ArchivedRecipeItem"]
        total: int
