"""Create ingredient endpoint."""

from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from utils.api.endpoint import Endpoint, APIException, success
from utils.classes.error_code import ErrorCode
from utils.models.ingredient import Ingredient
from utils.models.user import User


class CreateIngredient(Endpoint):
    """Create a new ingredient."""

    def execute(self, params: "CreateIngredient.Params"):
        """
        Create a new ingredient.

        New ingredients are created with pending_review=True for admin review.

        Args:
            params: Ingredient creation parameters

        Returns:
            Created ingredient data
        """
        user: User = self.user

        # Check if ingredient already exists
        existing = self.database.find_by(
            Ingredient,
            canonical_name=params.canonical_name.lower().strip()
        )
        if existing:
            raise APIException(
                status_code=400,
                detail=f"Ingredient '{params.canonical_name}' already exists",
                code=ErrorCode.DUPLICATE_INGREDIENT
            )

        # Create new ingredient
        ingredient = Ingredient(
            canonical_name=params.canonical_name.lower().strip(),
            category=params.category,
            default_unit=params.default_unit,
            pending_review=True,  # New user-submitted ingredients need review
            submitted_by_id=user.id
        )
        self.database.create(ingredient)
        self.database.db.refresh(ingredient)

        return success(
            data=CreateIngredient.Response(
                id=ingredient.id,
                canonical_name=ingredient.canonical_name,
                category=ingredient.category,
                default_unit=ingredient.default_unit,
                pending_review=ingredient.pending_review,
                created_at=ingredient.created_at
            ),
            status=201
        )

    class Params(BaseModel):
        canonical_name: str
        category: Optional[str] = None
        default_unit: Optional[str] = None

    class Response(BaseModel):
        id: str
        canonical_name: str
        category: Optional[str] = None
        default_unit: Optional[str] = None
        pending_review: bool
        created_at: datetime
