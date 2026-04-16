"""Add or upsert a pantry ingredient."""

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.ingredient import Ingredient
from utils.models.user import User
from utils.services.pantry_service import upsert_pantry_ingredient

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

        result = upsert_pantry_ingredient(
            self.database,
            pantry_id=pantry_id,
            ingredient_id=params.ingredient_id,
            quantity_display=params.quantity_display,
            unit_display=params.unit_display,
            quantity_normalized=params.quantity_normalized,
            unit_normalized=params.unit_normalized,
            storage_location=params.storage_location,
            expires_at=params.expires_at,
        )

        status = 201 if result.created else 200
        return success(
            data=format_pantry_ingredient(result.row, ingredient=ingredient),
            status=status,
        )
