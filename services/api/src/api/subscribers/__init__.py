"""Event subscribers for the in-process dispatcher.

Subscribers wire together libraries with side-effects (pantry mutations,
activity feed writes, push notifications) in response to domain events. The
``register_subscribers`` function is invoked once from the API lifespan.
"""

import logging

from utils.events import register

from .pantry_meal_subscriber import handle_meal_event_completed
from .pantry_shopping_subscriber import handle_shopping_list_item_purchased

logger = logging.getLogger(__name__)


def register_subscribers() -> None:
    """Register every event subscriber with the dispatcher."""
    register("ShoppingListItemPurchased", handle_shopping_list_item_purchased)
    register("MealEventCompleted", handle_meal_event_completed)
    logger.info(
        "registered subscribers: ShoppingListItemPurchased, MealEventCompleted"
    )
