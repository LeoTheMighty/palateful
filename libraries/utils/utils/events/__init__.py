"""In-process synchronous event dispatcher.

This is a tiny pub/sub layer for domain events fired post-commit within a
request. It is deliberately NOT a message queue: no Celery, no Redis, no
threading. Subscribers run inline in the caller's async context.

Used by the pantry hooks (pantry-3 / pantry-4) to react to shopping-list
purchases and completed meals without forcing those handlers to reach
directly into pantry modules.
"""

from .dispatcher import dispatch, register, unregister
from .events import MealEventCompleted, ShoppingListItemPurchased

__all__ = [
    "MealEventCompleted",
    "ShoppingListItemPurchased",
    "dispatch",
    "register",
    "unregister",
]
