"""Pantry mutation primitives usable from any context (HTTP, event subscribers, MCP).

These helpers operate on the synchronous SQLAlchemy session exposed by
``utils.services.database.Database``. They do NOT perform permission checks —
callers that receive untrusted input should gate access through the API
layer's ``require_pantry_access`` before calling here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from utils.models.pantry import Pantry
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.pantry_user import PantryUser

if TYPE_CHECKING:
    from utils.services.database import Database

logger = logging.getLogger(__name__)


@dataclass
class UpsertResult:
    """Return value of ``upsert_pantry_ingredient``."""

    row: PantryIngredient
    created: bool
    skipped_reason: str | None = None


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
    """Return (or lazily create) the caller's default pantry.

    MVP: every user has exactly one pantry. An advisory lock on
    ``default_pantry_{user_id}`` prevents concurrent first-time requests from
    creating duplicates.
    """
    membership = _find_default_membership(user_id, database)
    if membership:
        pantry = database.find_by(Pantry, id=membership.pantry_id)
        if pantry:
            return pantry, membership

    with database.lock(f"default_pantry_{user_id}"):
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


def upsert_pantry_ingredient(
    database: Database,
    *,
    pantry_id,
    ingredient_id,
    quantity_display: Decimal | float | int | None,
    unit_display: str | None,
    quantity_normalized: Decimal | float | int | None,
    unit_normalized: str | None,
    storage_location: str | None = None,
    expires_at: datetime | None = None,
) -> UpsertResult:
    """Insert a pantry ingredient, or sum quantity into an existing active row.

    If an active (non-archived) row for ``(pantry_id, ingredient_id)`` exists
    AND its ``unit_normalized`` matches the incoming value, the normalized
    quantities are summed. On unit mismatch the function logs at WARNING and
    returns the existing row unchanged with ``skipped_reason="unit_mismatch"``
    — this is the best-effort behavior required by the epic.
    """
    existing = (
        database.db.query(PantryIngredient)
        .filter(
            PantryIngredient.pantry_id == pantry_id,
            PantryIngredient.ingredient_id == ingredient_id,
            PantryIngredient.archived_at.is_(None),
        )
        .first()
    )

    quantity_normalized = Decimal(quantity_normalized) if quantity_normalized is not None else Decimal(0)
    quantity_display = Decimal(quantity_display) if quantity_display is not None else quantity_normalized

    if existing is not None:
        if (
            existing.unit_normalized
            and unit_normalized
            and existing.unit_normalized != unit_normalized
        ):
            logger.warning(
                "pantry_upsert_unit_mismatch pantry_id=%s ingredient_id=%s existing=%r incoming=%r",
                pantry_id,
                ingredient_id,
                existing.unit_normalized,
                unit_normalized,
            )
            return UpsertResult(row=existing, created=False, skipped_reason="unit_mismatch")

        existing.quantity_normalized = Decimal(existing.quantity_normalized) + quantity_normalized
        existing.quantity_display = quantity_display
        if unit_display is not None:
            existing.unit_display = unit_display
        if unit_normalized is not None:
            existing.unit_normalized = unit_normalized
        if storage_location is not None:
            existing.storage_location = storage_location
        if expires_at is not None:
            existing.expires_at = expires_at
        database.db.commit()
        database.db.refresh(existing)
        return UpsertResult(row=existing, created=False)

    row = PantryIngredient(
        pantry_id=pantry_id,
        ingredient_id=ingredient_id,
        quantity_display=quantity_display,
        unit_display=unit_display or "",
        quantity_normalized=quantity_normalized,
        unit_normalized=unit_normalized or "",
        storage_location=storage_location,
        expires_at=expires_at,
    )
    database.create(row)
    return UpsertResult(row=row, created=True)


def soft_delete_pantry_ingredient(
    database: Database, *, pantry_id, ingredient_id
) -> PantryIngredient | None:
    """Idempotent soft-delete. Returns the row (or None if it never existed)."""
    row = (
        database.db.query(PantryIngredient)
        .filter(
            PantryIngredient.pantry_id == pantry_id,
            PantryIngredient.ingredient_id == ingredient_id,
        )
        .first()
    )
    if row is None:
        return None
    if row.archived_at is None:
        row.archived_at = datetime.now(UTC)
        database.db.commit()
    return row
