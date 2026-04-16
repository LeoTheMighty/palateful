"""Event payload dataclasses dispatched via the in-process dispatcher."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ShoppingListItemPurchased:
    """Emitted when a shopping-list item transitions from unchecked → checked.

    Only dispatched when ``ingredient_id`` is non-null; free-text items are
    not represented.
    """

    user_id: uuid.UUID
    shopping_list_id: uuid.UUID
    item_id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity_normalized: Decimal | None
    unit_normalized: str | None
    shopping_list_item_name: str


@dataclass(frozen=True)
class MealEventCompleted:
    """Emitted when a meal_event transitions into the ``completed`` status."""

    user_id: uuid.UUID
    meal_event_id: uuid.UUID
    recipe_id: uuid.UUID
    servings: float | None
