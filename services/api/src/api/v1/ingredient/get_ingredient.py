"""Get ingredient endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.ingredient import Ingredient


class GetIngredient(Endpoint):
    """Get ingredient by ID."""

    def execute(self, ingredient_id: str):
        """
        Get ingredient details by ID.

        Args:
            ingredient_id: The ingredient's ID

        Returns:
            Ingredient details
        """
        ingredient = self.database.find_by(Ingredient, id=ingredient_id)

        if not ingredient:
            raise APIException(
                status_code=404,
                detail=f"Ingredient with ID '{ingredient_id}' not found",
                code=ErrorCode.INGREDIENT_NOT_FOUND
            )

        return success(
            data=GetIngredient.Response(
                id=ingredient.id,
                canonical_name=ingredient.canonical_name,
                aliases=ingredient.aliases or [],
                category=ingredient.category,
                flavor_profile=ingredient.flavor_profile or [],
                default_unit=ingredient.default_unit,
                is_canonical=ingredient.is_canonical,
                pending_review=ingredient.pending_review,
                image_url=ingredient.image_url,
                created_at=ingredient.created_at
            )
        )

    class Response(BaseModel):
        id: str
        canonical_name: str
        aliases: list[str] = []
        category: str | None = None
        flavor_profile: list[str] = []
        default_unit: str | None = None
        is_canonical: bool = True
        pending_review: bool = False
        image_url: str | None = None
        created_at: datetime
