"""Shared ingredient find-or-create helper.

Every surface that accepts user-typed ingredient input — the recipe-create
endpoint, the recipe-update endpoint, and the import-task ingredient
persister — funnels through [resolve_ingredient] so the find-or-create
rule (canonical_name normalization, pending_review flag, submitted_by_id)
lives in exactly one place.

Reference: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`
`_create_recipe_ingredient` was the original implementation; this helper
extracts it so the FastAPI endpoints in
`services/api/src/api/v1/recipe/create_recipe.py` and `update_recipe.py`
no longer reject inputs lacking an `ingredient_id`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from utils.models.ingredient import Ingredient

if TYPE_CHECKING:
    from utils.services.database import Database

logger = logging.getLogger(__name__)


class IngredientResolutionError(ValueError):
    """Raised when `resolve_ingredient` cannot produce a row.

    Endpoints should translate this into an `APIException(400,
    ErrorCode.INGREDIENT_INPUT_REQUIRED)` or
    `ErrorCode.INGREDIENT_NOT_FOUND` as appropriate. Keeping the raise
    decoupled from FastAPI keeps the helper importable from the worker
    (Celery tasks) too.
    """


def resolve_ingredient(
    database: Database,
    *,
    ingredient_id: str | None = None,
    name: str | None = None,
    submitted_by_id: str | None = None,
) -> Ingredient:
    """Find an ingredient by id, or find-or-create by name.

    Args:
        database: Active `Database` wrapper (shared advisory-lock path).
        ingredient_id: Canonical UUID. Wins when present — guards against
            name-drift on known-good ingredients (e.g., a client sends a
            typo as `name` along with the real `ingredient_id`).
        name: Human-typed name. Lowercased + stripped + used as the
            `canonical_name` for `find_or_create_by`.
        submitted_by_id: User id to stamp on newly-created rows.

    Returns:
        Ingredient row (existing or newly-created, `pending_review=True`).

    Raises:
        IngredientResolutionError: if neither `ingredient_id` nor a
            non-empty `name` is supplied, or if `ingredient_id` is
            provided but doesn't match an existing row.
    """
    if ingredient_id:
        ingredient = database.find_by(Ingredient, id=ingredient_id)
        if not ingredient:
            raise IngredientResolutionError(
                f"Ingredient with ID '{ingredient_id}' not found"
            )
        return ingredient

    if name is None or not name.strip():
        raise IngredientResolutionError(
            "Either ingredient_id or a non-empty name is required"
        )

    canonical = name.strip().lower()
    return database.find_or_create_by(
        Ingredient,
        defaults={
            "is_canonical": False,
            "pending_review": True,
            "submitted_by_id": submitted_by_id,
        },
        canonical_name=canonical,
    )
