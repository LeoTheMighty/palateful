"""Pantry mutation primitives usable from any context (HTTP, event subscribers, MCP).

Two parallel surfaces live here:

* The historic synchronous helpers operate on
  ``utils.services.database.Database`` and remain the surface used by
  ``services/api/src/api/subscribers/pantry_meal_subscriber.py`` and
  ``services/api/src/api/v1/shopping_list/update_item.py`` (both still
  synchronous at time of writing — aam-13 / aam-14 backlog).
* The ``*_async`` mirrors operate on ``AsyncDatabase`` (aam-15 added,
  used by the ``AsyncEndpoint`` pantry handlers).

Neither path performs permission checks — callers that receive untrusted
input should gate access through the API layer's ``require_pantry_access``
(or ``require_pantry_access_async``) before calling here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from utils.models.pantry import Pantry
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.pantry_ingredient_event import PantryIngredientEvent
from utils.models.pantry_user import PantryUser

if TYPE_CHECKING:
    from utils.services.async_database import AsyncDatabase
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


@dataclass
class DecrementOutcome:
    """Result summary of ``decrement_pantry_from_recipe``."""

    decremented: list[PantryIngredientEvent]
    skipped_unit_mismatch: int
    skipped_missing_pantry_row: int
    skipped_invalid_recipe_data: int


def decrement_pantry_from_recipe(
    database: Database,
    *,
    pantry_id,
    recipe,
    servings_scale: float = 1.0,
    source_meal_event_id=None,
) -> DecrementOutcome:
    """Decrement pantry quantities for every ingredient on ``recipe``.

    Best-effort: strict string match on ``unit_normalized``. On mismatch,
    logs at WARNING and skips (never raises, never prompts). Writes an
    audit row to ``pantry_ingredient_events`` for each actual decrement.
    Quantities clamp at zero; a decrement that reaches zero also archives
    the pantry row.

    **Sync-only.** No async twin exists because the only caller today is
    ``pantry_meal_subscriber`` (sync event dispatcher). Async handlers
    that need this logic must dispatch via ``run_in_threadpool`` with a
    fresh ``Database(db=SessionLocal())`` — the query loop here holds a
    sync session across many mutations and a greenlet bridge would be
    the wrong fix.
    """
    decremented: list[PantryIngredientEvent] = []
    skipped_unit_mismatch = 0
    skipped_missing_pantry_row = 0
    skipped_invalid_recipe_data = 0

    for ri in getattr(recipe, "ingredients", []) or []:
        if ri.quantity_normalized is None or ri.unit_normalized is None:
            skipped_invalid_recipe_data += 1
            logger.warning(
                "pantry_decrement_skip_invalid_recipe_data recipe_id=%s ingredient_id=%s",
                getattr(recipe, "id", None),
                ri.ingredient_id,
            )
            continue

        consumed = Decimal(ri.quantity_normalized) * Decimal(str(servings_scale))

        row = (
            database.db.query(PantryIngredient)
            .filter(
                PantryIngredient.pantry_id == pantry_id,
                PantryIngredient.ingredient_id == ri.ingredient_id,
                PantryIngredient.archived_at.is_(None),
            )
            .first()
        )
        if row is None:
            skipped_missing_pantry_row += 1
            logger.debug(
                "pantry_decrement_skip_missing_row pantry_id=%s ingredient_id=%s",
                pantry_id,
                ri.ingredient_id,
            )
            continue

        if row.unit_normalized != ri.unit_normalized:
            # Epic rule: best-effort, silent skip on unit mismatch.
            skipped_unit_mismatch += 1
            logger.warning(
                "pantry_decrement_skip_unit_mismatch pantry_id=%s ingredient_id=%s "
                "pantry_unit=%r recipe_unit=%r",
                pantry_id,
                ri.ingredient_id,
                row.unit_normalized,
                ri.unit_normalized,
            )
            continue

        before = Decimal(row.quantity_normalized)
        after = before - consumed
        if after < 0:
            after = Decimal(0)
            # delta is the actual amount removed, not the attempted amount.
            delta = before
        else:
            delta = consumed

        row.quantity_normalized = after
        if after == 0:
            row.archived_at = datetime.now(UTC)

        event = PantryIngredientEvent(
            pantry_id=pantry_id,
            ingredient_id=ri.ingredient_id,
            event_type="decrement",
            delta_quantity=-delta,
            source_meal_event_id=source_meal_event_id,
        )
        database.db.add(event)
        decremented.append(event)

        logger.info(
            "pantry_auto_decrement pantry_id=%s ingredient_id=%s from=%s to=%s",
            pantry_id,
            ri.ingredient_id,
            before,
            after,
        )

    if decremented or skipped_unit_mismatch or skipped_missing_pantry_row:
        database.db.commit()

    return DecrementOutcome(
        decremented=decremented,
        skipped_unit_mismatch=skipped_unit_mismatch,
        skipped_missing_pantry_row=skipped_missing_pantry_row,
        skipped_invalid_recipe_data=skipped_invalid_recipe_data,
    )


# ─────────────────────────────── Async mirrors (aam-15) ─────────────────────
#
# `*_async` twins of the mutation helpers, for `AsyncEndpoint` handlers.
# Semantics are preserved 1:1 with their sync counterparts above; any
# behavior change must land in both halves until the sync variants
# retire in the post-cutover cleanup epic.


async def _find_default_membership_async(
    user_id, database: AsyncDatabase
) -> PantryUser | None:
    stmt = (
        select(PantryUser)
        .where(
            PantryUser.user_id == user_id,
            PantryUser.archived_at.is_(None),
        )
        .order_by(PantryUser.created_at.asc())
        .limit(1)
    )
    result = await database.db.execute(stmt)
    return result.scalars().first()


async def get_or_create_default_pantry_async(
    user_id, database: AsyncDatabase
) -> tuple[Pantry, PantryUser]:
    """Async mirror of ``get_or_create_default_pantry``."""
    membership = await _find_default_membership_async(user_id, database)
    if membership:
        pantry = await database.find_by(Pantry, id=membership.pantry_id)
        if pantry:
            return pantry, membership

    async with database.lock(f"default_pantry_{user_id}"):
        membership = await _find_default_membership_async(user_id, database)
        if membership:
            pantry = await database.find_by(Pantry, id=membership.pantry_id)
            if pantry:
                return pantry, membership

        pantry = Pantry(name="My Pantry")
        await database.create(pantry)
        membership = PantryUser(
            user_id=user_id,
            pantry_id=pantry.id,
            role="owner",
        )
        await database.create(membership)
        return pantry, membership


async def upsert_pantry_ingredient_async(
    database: AsyncDatabase,
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
    """Async mirror of ``upsert_pantry_ingredient``."""
    existing_stmt = (
        select(PantryIngredient)
        .where(
            PantryIngredient.pantry_id == pantry_id,
            PantryIngredient.ingredient_id == ingredient_id,
            PantryIngredient.archived_at.is_(None),
        )
        .limit(1)
    )
    existing = (await database.db.execute(existing_stmt)).scalars().first()

    quantity_normalized = (
        Decimal(quantity_normalized) if quantity_normalized is not None else Decimal(0)
    )
    quantity_display = (
        Decimal(quantity_display) if quantity_display is not None else quantity_normalized
    )

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
            return UpsertResult(
                row=existing, created=False, skipped_reason="unit_mismatch"
            )

        existing.quantity_normalized = (
            Decimal(existing.quantity_normalized) + quantity_normalized
        )
        existing.quantity_display = quantity_display
        if unit_display is not None:
            existing.unit_display = unit_display
        if unit_normalized is not None:
            existing.unit_normalized = unit_normalized
        if storage_location is not None:
            existing.storage_location = storage_location
        if expires_at is not None:
            existing.expires_at = expires_at
        await database.db.commit()
        await database.db.refresh(existing)
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
    await database.create(row)
    return UpsertResult(row=row, created=True)


async def soft_delete_pantry_ingredient_async(
    database: AsyncDatabase, *, pantry_id, ingredient_id
) -> PantryIngredient | None:
    """Async mirror of ``soft_delete_pantry_ingredient``."""
    stmt = (
        select(PantryIngredient)
        .where(
            PantryIngredient.pantry_id == pantry_id,
            PantryIngredient.ingredient_id == ingredient_id,
        )
        .limit(1)
    )
    row = (await database.db.execute(stmt)).scalars().first()
    if row is None:
        return None
    if row.archived_at is None:
        row.archived_at = datetime.now(UTC)
        await database.db.commit()
    return row
