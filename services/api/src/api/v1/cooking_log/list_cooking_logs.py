"""List cooking logs endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.cooking_log import CookingLog
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ListCookingLogs(AsyncEndpoint):
    """List recently cooked recipes for the current user."""

    async def execute(self, limit: int = 10):
        """
        List the most recent cooking log entries for the current user.

        Scopes to the current user by joining CookingLog → Recipe → RecipeBookUser.
        Returns the most recent entries ordered by cooked_at descending.

        Args:
            limit: Maximum number of results (default 10, max 50)

        Returns:
            List of recently cooked recipe summaries.
        """
        user: User = self.user

        # Fetch extra rows to ensure enough distinct recipes after deduplication
        stmt = (
            select(CookingLog, Recipe)
            .join(Recipe, CookingLog.recipe_id == Recipe.id)
            .join(
                RecipeBookUser,
                (RecipeBookUser.recipe_book_id == Recipe.recipe_book_id)
                & (RecipeBookUser.user_id == user.id),
            )
            .where(Recipe.archived_at.is_(None))
            .where(CookingLog.archived_at.is_(None))
            .order_by(CookingLog.cooked_at.desc())
            .limit(limit * 3)
        )
        result = await self.database.db.execute(stmt)
        raw_results = result.all()

        # Deduplicate: keep only the most recent log per recipe
        seen: set[str] = set()
        deduped: list[tuple] = []
        for log, recipe in raw_results:
            recipe_id_str = str(recipe.id)
            if recipe_id_str not in seen:
                seen.add(recipe_id_str)
                deduped.append((log, recipe))
                if len(deduped) == limit:
                    break

        items = [
            ListCookingLogs.CookingLogItem(
                recipe_id=str(recipe.id),
                recipe_name=recipe.name,
                recipe_image_url=recipe.image_url,
                cooked_at=log.cooked_at,
            )
            for log, recipe in deduped
        ]

        return success(
            data=ListCookingLogs.Response(
                items=items,
                total=len(items),
            )
        )

    class CookingLogItem(BaseModel):
        recipe_id: str
        recipe_name: str
        recipe_image_url: str | None = None
        cooked_at: datetime

    class Response(BaseModel):
        items: list["ListCookingLogs.CookingLogItem"]
        total: int
