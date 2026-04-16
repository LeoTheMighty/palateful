"""Shared helpers for pantry endpoints."""

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.pantry import Pantry
from utils.models.pantry_user import PantryUser
from utils.services.database import Database

from .schemas import PantryIngredientRead


def _find_default_membership(user_id, database: Database) -> PantryUser | None:
    return (
        database.db.query(PantryUser)
        .filter(
            PantryUser.user_id == user_id,
            PantryUser.archived_at.is_(None),
        )
        .order_by(PantryUser.created_at.asc())
        .first()
    )


def get_or_create_default_pantry(user_id, database: Database) -> tuple[Pantry, PantryUser]:
    """Return the caller's default pantry, creating it lazily if missing.

    MVP: every user has exactly one pantry. First access creates a pantry with
    the caller as owner. An advisory lock scoped to the user guards against
    two concurrent requests each creating a pantry.
    """
    membership = _find_default_membership(user_id, database)
    if membership:
        pantry = database.find_by(Pantry, id=membership.pantry_id)
        if pantry:
            return pantry, membership

    with database.lock(f"default_pantry_{user_id}"):
        # Re-check inside the lock in case another request raced us.
        membership = _find_default_membership(user_id, database)
        if membership:
            pantry = database.find_by(Pantry, id=membership.pantry_id)
            if pantry:
                return pantry, membership

        pantry = Pantry(name="My Pantry")
        database.create(pantry)
        membership = PantryUser(
            user_id=user_id,
            pantry_id=pantry.id,
            role="owner",
        )
        database.create(membership)
        return pantry, membership


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

    ``ingredient`` overrides row.ingredient when provided — useful when the
    caller already has the ORM Ingredient object in hand and wants to avoid
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
