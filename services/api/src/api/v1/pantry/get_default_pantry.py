"""Get (or lazily create) the caller's default pantry."""

from sqlalchemy.orm import selectinload
from utils.api.endpoint import Endpoint, success
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.user import User

from .helpers import format_pantry_ingredient, get_or_create_default_pantry
from .schemas import PantryRead


class GetDefaultPantry(Endpoint):
    """GET /pantries/default — lazy-create a pantry if the user has none."""

    def execute(self):
        user: User = self.user
        pantry, membership = get_or_create_default_pantry(user.id, self.database)

        rows = (
            self.database.db.query(PantryIngredient)
            .options(selectinload(PantryIngredient.ingredient))
            .filter(
                PantryIngredient.pantry_id == pantry.id,
                PantryIngredient.archived_at.is_(None),
            )
            .all()
        )

        return success(
            data=PantryRead(
                id=str(pantry.id),
                name=pantry.name,
                role=membership.role,
                items=[format_pantry_ingredient(r) for r in rows],
            )
        )
