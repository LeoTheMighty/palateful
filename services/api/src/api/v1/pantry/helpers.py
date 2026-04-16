"""API-layer helpers for pantry endpoints.

Core mutation logic lives in ``utils.services.pantry_service``; this module
adds HTTP-specific concerns (permission checks, response shaping).
"""

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.pantry import Pantry
from utils.models.pantry_user import PantryUser
from utils.services.database import Database
from utils.services.pantry_service import (
    get_or_create_default_pantry,
)

from .schemas import PantryIngredientRead

__all__ = [
    "format_pantry_ingredient",
    "get_or_create_default_pantry",
    "require_pantry_access",
]


def require_pantry_access(
    user_id,
    pantry_id,
    database: Database,
    *,
    mutate: bool,
) -> PantryUser:
    """Require the caller to have access to the pantry.

    If ``mutate`` is True, require owner or editor. Otherwise any active
    member role is enough. Raises 404 when the pantry does not exist and
    403 when the user is not a member with sufficient role.
    """
    pantry = database.find_by(Pantry, id=pantry_id)
    if not pantry:
        raise APIException(
            status_code=404,
            detail=f"Pantry with ID '{pantry_id}' not found",
            code=ErrorCode.PANTRY_NOT_FOUND,
        )

    membership = (
        database.db.query(PantryUser)
        .filter(
            PantryUser.user_id == user_id,
            PantryUser.pantry_id == pantry.id,
            PantryUser.archived_at.is_(None),
        )
        .first()
    )

    if not membership:
        raise APIException(
            status_code=403,
            detail="You don't have access to this pantry",
            code=ErrorCode.PANTRY_ACCESS_DENIED,
        )

    if mutate and membership.role not in ("owner", "editor"):
        raise APIException(
            status_code=403,
            detail="You don't have permission to modify this pantry",
            code=ErrorCode.PANTRY_ACCESS_DENIED,
        )

    return membership


def format_pantry_ingredient(row, ingredient=None) -> PantryIngredientRead:
    """Serialize a PantryIngredient ORM row to the API read schema.

    ``ingredient`` overrides ``row.ingredient`` when provided — useful when
    the caller already has the ORM Ingredient in hand and wants to avoid
    round-tripping through the relationship loader.
    """
    source = ingredient if ingredient is not None else getattr(row, "ingredient", None)
    return PantryIngredientRead(
        pantry_id=str(row.pantry_id),
        ingredient_id=str(row.ingredient_id),
        ingredient_name=getattr(source, "canonical_name", None),
        category=getattr(source, "category", None),
        quantity_display=row.quantity_display,
        unit_display=row.unit_display,
        quantity_normalized=row.quantity_normalized,
        unit_normalized=row.unit_normalized,
        storage_location=row.storage_location,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        archived_at=row.archived_at,
    )
