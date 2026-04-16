"""Soft-delete a pantry ingredient."""

from datetime import UTC, datetime

from utils.api.endpoint import Endpoint, success
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.user import User

from .helpers import require_pantry_access


class DeletePantryIngredient(Endpoint):
    """DELETE /pantries/{pantry_id}/ingredients/{ingredient_id} — idempotent soft delete."""

    def execute(self, pantry_id: str, ingredient_id: str):
        user: User = self.user
        require_pantry_access(user.id, pantry_id, self.database, mutate=True)

        row = (
            self.database.db.query(PantryIngredient)
            .filter(
                PantryIngredient.pantry_id == pantry_id,
                PantryIngredient.ingredient_id == ingredient_id,
            )
            .first()
        )
        if row and row.archived_at is None:
            row.archived_at = datetime.now(UTC)
            self.database.db.commit()

        return success(
            data={
                "deleted": True,
                "pantry_id": pantry_id,
                "ingredient_id": ingredient_id,
            }
        )
