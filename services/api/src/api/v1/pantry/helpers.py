"""API-layer helpers for pantry endpoints.

Core mutation logic lives in ``utils.services.pantry_service``; this module
adds HTTP-specific concerns (permission checks, response shaping).

aam-15: sync ``require_pantry_access`` retired — every API caller is
async now (``AddPantryIngredient``, ``UpdatePantryIngredient``,
``DeletePantryIngredient``, ``EstimateExpiry``, ``GetDefaultPantry``).
Subscribers never called this helper; they operate below the HTTP
permission layer by design.
"""

from sqlalchemy import select
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.pantry import Pantry
from utils.models.pantry_user import PantryUser
from utils.services.async_database import AsyncDatabase
from utils.services.pantry_service import (
    get_or_create_default_pantry,
    get_or_create_default_pantry_async,
)

from .schemas import PantryIngredientRead

__all__ = [
    "format_pantry_ingredient",
    "get_or_create_default_pantry",
    "get_or_create_default_pantry_async",
    "require_pantry_access_async",
]


async def require_pantry_access_async(
    user_id,
    pantry_id,
    database: AsyncDatabase,
    *,
    mutate: bool,
) -> PantryUser:
    """Async mirror of ``require_pantry_access``.

    Preserves the 404 / 403 split and the owner/editor write-gate.
    """
    pantry = await database.find_by(Pantry, id=pantry_id)
    if not pantry:
        raise APIException(
            status_code=404,
            detail=f"Pantry with ID '{pantry_id}' not found",
            code=ErrorCode.PANTRY_NOT_FOUND,
        )

    stmt = (
        select(PantryUser)
        .where(
            PantryUser.user_id == user_id,
            PantryUser.pantry_id == pantry.id,
            PantryUser.archived_at.is_(None),
        )
        .limit(1)
    )
    membership = (await database.db.execute(stmt)).scalars().first()

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
