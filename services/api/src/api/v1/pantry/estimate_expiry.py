"""Expose the shelf-life estimator over HTTP for the pantry editor (pantry-6)."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.ingredient import Ingredient
from utils.models.user import User
from utils.services.shelf_life_service import estimate_expires_at

from .helpers import require_pantry_access
from .schemas import StorageLocation


class EstimateExpiry(Endpoint):
    """POST /pantries/{pantry_id}/estimate-expiry — thin wrapper over shelf_life_service."""

    def execute(self, pantry_id: str, params: "EstimateExpiry.Params"):
        user: User = self.user
        # Any pantry member can estimate (read-only).
        require_pantry_access(user.id, pantry_id, self.database, mutate=False)

        ingredient = self.database.find_by(Ingredient, id=params.ingredient_id)
        if not ingredient:
            raise APIException(
                status_code=404,
                detail=f"Ingredient with ID '{params.ingredient_id}' not found",
                code=ErrorCode.INGREDIENT_NOT_FOUND,
            )

        expires_at = estimate_expires_at(ingredient, params.storage_location)
        return success(data=EstimateExpiry.Response(expires_at=expires_at))

    class Params(BaseModel):
        ingredient_id: str
        storage_location: StorageLocation

    class Response(BaseModel):
        expires_at: datetime | None
