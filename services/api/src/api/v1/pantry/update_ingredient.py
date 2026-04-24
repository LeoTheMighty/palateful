"""Update a pantry ingredient."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.user import User

from .helpers import format_pantry_ingredient, require_pantry_access_async
from .schemas import PantryIngredientUpdate


class UpdatePantryIngredient(AsyncEndpoint):
    """PATCH /pantries/{pantry_id}/ingredients/{ingredient_id}."""

    async def execute(
        self, pantry_id: str, ingredient_id: str, params: PantryIngredientUpdate
    ):
        user: User = self.user
        await require_pantry_access_async(
            user.id, pantry_id, self.database, mutate=True
        )

        # Eager-load `ingredient` — `format_pantry_ingredient(row)` below
        # reads `row.ingredient.canonical_name` / `.category`, which on
        # an AsyncSession raises `MissingGreenlet` if the relationship
        # isn't loaded at query time.
        stmt = (
            select(PantryIngredient)
            .options(selectinload(PantryIngredient.ingredient))
            .where(
                PantryIngredient.pantry_id == pantry_id,
                PantryIngredient.ingredient_id == ingredient_id,
                PantryIngredient.archived_at.is_(None),
            )
            .limit(1)
        )
        row = (await self.db.execute(stmt)).scalars().first()
        if not row:
            raise APIException(
                status_code=404,
                detail="Pantry item not found",
                code=ErrorCode.PANTRY_INGREDIENT_NOT_FOUND,
            )

        if params.quantity_display is not None:
            row.quantity_display = params.quantity_display
        if params.unit_display is not None:
            row.unit_display = params.unit_display
        if params.quantity_normalized is not None:
            new_quantity = Decimal(params.quantity_normalized)
            if new_quantity < 0:
                new_quantity = Decimal(0)
            row.quantity_normalized = new_quantity
            if new_quantity == 0:
                # Never go negative: clamp and auto-archive so "use it all up" is one PATCH.
                row.archived_at = datetime.now(UTC)
        if params.unit_normalized is not None:
            row.unit_normalized = params.unit_normalized
        if params.storage_location is not None:
            row.storage_location = params.storage_location
        if params.expires_at is not None:
            row.expires_at = params.expires_at

        await self.db.commit()
        await self.db.refresh(row)
        return success(data=format_pantry_ingredient(row))
