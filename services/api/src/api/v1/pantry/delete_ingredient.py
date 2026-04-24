"""Soft-delete a pantry ingredient."""

from datetime import UTC, datetime

from sqlalchemy import select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.user import User

from .helpers import require_pantry_access_async


class DeletePantryIngredient(AsyncEndpoint):
    """DELETE /pantries/{pantry_id}/ingredients/{ingredient_id} — idempotent soft delete."""

    async def execute(self, pantry_id: str, ingredient_id: str):
        user: User = self.user
        await require_pantry_access_async(
            user.id, pantry_id, self.database, mutate=True
        )

        stmt = (
            select(PantryIngredient)
            .where(
                PantryIngredient.pantry_id == pantry_id,
                PantryIngredient.ingredient_id == ingredient_id,
            )
            .limit(1)
        )
        row = (await self.db.execute(stmt)).scalars().first()
        if row and row.archived_at is None:
            row.archived_at = datetime.now(UTC)
            await self.db.commit()

        return success(
            data={
                "deleted": True,
                "pantry_id": pantry_id,
                "ingredient_id": ingredient_id,
            }
        )
