"""Subscriber for ``ShoppingListItemPurchased``.

The pantry upsert itself happens INLINE in the
``UpdateShoppingListItem`` handler so that the response can include the new
``pantry_ingredient_id`` for the Flutter snackbar / undo UX. This subscriber
exists for fan-out — future subscribers (telemetry, push notifications,
partner activity feed) can hook in here without touching the shopping-list
handler.
"""

import logging

from utils.events import ShoppingListItemPurchased

logger = logging.getLogger(__name__)


def handle_shopping_list_item_purchased(event: ShoppingListItemPurchased) -> None:
    logger.info(
        "pantry_auto_add user_id=%s ingredient_id=%s quantity_normalized=%s unit=%s item=%r",
        event.user_id,
        event.ingredient_id,
        event.quantity_normalized,
        event.unit_normalized,
        event.shopping_list_item_name,
    )
