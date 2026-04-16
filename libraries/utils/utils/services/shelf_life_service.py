"""Shelf-life estimation service.

Loads a static seed JSON mapping `ingredient.category` × storage_location
(fridge / pantry / freezer) to a day count, then computes `expires_at` as
`added_at + timedelta(days=N)`. Returns `None` when the lookup has no value
(ingredient shouldn't be stored that way) or when `storage_location` is
unknown. Never performs I/O beyond the one-time JSON load.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.models.ingredient import Ingredient

logger = logging.getLogger(__name__)

_CACHE: dict | None = None
_SHELF_LIFE_PATH = Path(__file__).resolve().parent.parent / "data" / "shelf_life.json"

_VALID_DAY_KEYS = ("fridge_days", "pantry_days", "freezer_days")


def _validate_shape(data: dict) -> None:
    if "_default" not in data:
        raise ValueError("shelf_life.json is missing the '_default' key")
    for category, values in data.items():
        if not isinstance(values, dict):
            raise ValueError(f"shelf_life.json['{category}'] is not an object")
        for key in _VALID_DAY_KEYS:
            if key not in values:
                raise ValueError(
                    f"shelf_life.json['{category}'] is missing key '{key}'"
                )
            val = values[key]
            if val is None:
                continue
            if not isinstance(val, int) or val <= 0:
                raise ValueError(
                    f"shelf_life.json['{category}']['{key}'] must be a positive int or null; got {val!r}"
                )


def load_shelf_life_data() -> dict:
    """Load and cache the shelf-life JSON. First call parses from disk.

    Raises ValueError at startup if the JSON is malformed so a bad deployment
    fails fast rather than on the first ingredient addition.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    with _SHELF_LIFE_PATH.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    _validate_shape(data)
    _CACHE = data
    return _CACHE


def _reset_cache_for_tests() -> None:
    """Test-only hook to force a re-load of the JSON."""
    global _CACHE
    _CACHE = None


def estimate_expires_at(
    ingredient: Ingredient | None,
    storage_location: str | None,
    added_at: datetime | None = None,
) -> datetime | None:
    """Estimate when an item will expire.

    Returns ``None`` when ``storage_location`` is unknown, when the category
    lookup returns ``null`` for that location (e.g. leafy greens at pantry
    temp), or when the JSON has no matching entry.
    """
    if storage_location is None:
        return None
    if storage_location not in ("fridge", "pantry", "freezer"):
        return None

    data = load_shelf_life_data()
    category = getattr(ingredient, "category", None) if ingredient is not None else None
    entry = data.get(category) if category else None
    if entry is None:
        entry = data["_default"]

    days = entry.get(f"{storage_location}_days")
    if days is None:
        return None

    base = added_at if added_at is not None else datetime.now(UTC)
    return base + timedelta(days=days)
