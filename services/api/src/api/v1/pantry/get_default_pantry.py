"""Get (or lazily create) the caller's default pantry."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.user import User

from .helpers import format_pantry_ingredient, get_or_create_default_pantry_async
from .schemas import PantryRead


class GetDefaultPantry(AsyncEndpoint):
    """GET /pantries/default — lazy-create a pantry if the user has none."""

    async def execute(self):
        user: User = self.user
        pantry, membership = await get_or_create_default_pantry_async(
            user.id, self.database
        )

        stmt = (
            select(PantryIngredient)
            .options(selectinload(PantryIngredient.ingredient))
            .where(
                PantryIngredient.pantry_id == pantry.id,
                PantryIngredient.archived_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        return success(
            data=PantryRead(
                id=str(pantry.id),
                name=pantry.name,
                role=membership.role,
                items=[format_pantry_ingredient(r) for r in rows],
            )
        )
