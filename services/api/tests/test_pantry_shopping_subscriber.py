"""Smoke test for the shopping-list → pantry subscriber's fan-out body."""

import uuid
from decimal import Decimal

from utils.events import ShoppingListItemPurchased


def test_handler_logs_without_raising():
    from api.subscribers.pantry_shopping_subscriber import (
        handle_shopping_list_item_purchased,
    )

    # The subscriber exists for fan-out only; today it just logs. Make sure
    # it runs to completion given a well-formed payload.
    handle_shopping_list_item_purchased(
        ShoppingListItemPurchased(
            user_id=uuid.uuid4(),
            shopping_list_id=uuid.uuid4(),
            item_id=uuid.uuid4(),
            ingredient_id=uuid.uuid4(),
            quantity_normalized=Decimal("1"),
            unit_normalized="each",
            shopping_list_item_name="onion",
        )
    )
