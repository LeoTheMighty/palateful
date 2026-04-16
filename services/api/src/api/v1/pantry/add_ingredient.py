"""Add or upsert a pantry ingredient."""

from decimal import Decimal

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.ingredient import Ingredient
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.user import User

from .helpers import format_pantry_ingredient, require_pantry_access
from .schemas import PantryIngredientCreate


class AddPantryIngredient(Endpoint):
    """POST /pantries/{pantry_id}/ingredients — insert or upsert-by-quantity."""

    def execute(self, pantry_id: str, params: PantryIngredientCreate):
        user: User = self.user
        require_pantry_access(user.id, pantry_id, self.database, mutate=True)

        ingredient = self.database.find_by(Ingredient, id=params.ingredient_id)
        if not ingredient:
            raise APIException(
                status_code=404,
                detail=f"Ingredient with ID '{params.ingredient_id}' not found",
                code=ErrorCode.INGREDIENT_NOT_FOUND,
            )

        existing = (
            self.database.db.query(PantryIngredient)
            .filter(
                PantryIngredient.pantry_id == pantry_id,
                PantryIngredient.ingredient_id == params.ingredient_id,
                PantryIngredient.archived_at.is_(None),
            )
            .first()
        )

        if existing:
            # Upsert: add incoming normalized quantity. Display quantity is best-effort
            # updated to the new value (we can't safely sum display strings across units).
            existing.quantity_normalized = (
                Decimal(existing.quantity_normalized) + Decimal(params.quantity_normalized)
            )
            existing.quantity_display = params.quantity_display
            existing.unit_display = params.unit_display
            existing.unit_normalized = params.unit_normalized
            if params.storage_location is not None:
                existing.storage_location = params.storage_location
            if params.expires_at is not None:
                existing.expires_at = params.expires_at
            self.database.db.commit()
            self.database.db.refresh(existing)
            row = existing
            status = 200
        else:
            row = PantryIngredient(
                pantry_id=pantry_id,
                ingredient_id=params.ingredient_id,
                quantity_display=params.quantity_display,
                unit_display=params.unit_display,
                quantity_normalized=params.quantity_normalized,
                unit_normalized=params.unit_normalized,
                storage_location=params.storage_location,
                expires_at=params.expires_at,
            )
            self.database.create(row)
            status = 201

        return success(
            data=format_pantry_ingredient(row, ingredient=ingredient),
            status=status,
        )
