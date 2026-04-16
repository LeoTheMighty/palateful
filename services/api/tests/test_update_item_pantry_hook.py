"""Integration-ish tests for the shopping-list → pantry hook (pantry-3).

These use the same mocking pattern as the rest of the suite — the assertion
is that ``database.create`` is called with a ``PantryIngredient`` row and
that the response body surfaces ``pantry_ingredient_id`` for the client's
snackbar/undo UX.
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

from conftest import (
    MockPantry,
    MockPantryUser,
    MockQuery,
    MockShoppingList,
    MockShoppingListItem,
)


def _query_router(mock_db, by_model: dict):
    def side_effect(model_class, *args, **kwargs):
        items = by_model.get(model_class)
        if items is None:
            return MockQuery([])
        return items if isinstance(items, MockQuery) else MockQuery(items)
    mock_db.db.query.side_effect = side_effect


class TestPantryHookFires:
    def test_check_with_ingredient_populates_pantry_fields(
        self, client, mock_db, mock_user
    ):
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            is_checked=False,
            ingredient_id=ingredient_id,
            quantity=Decimal("2"),
            unit="each",
            name="onion",
        )
        pantry = MockPantry()
        membership = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=str(pantry.id), role="owner"
        )

        from utils.models.pantry import Pantry
        from utils.models.pantry_ingredient import PantryIngredient
        from utils.models.pantry_user import PantryUser
        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListItem, item, id=item_id, shopping_list_id=list_id
        )
        mock_db.set_find_by(Pantry, pantry, id=pantry.id)
        _query_router(
            mock_db,
            {
                PantryUser: [membership],
                PantryIngredient: [],
                ShoppingListItem: [],  # unchecked_count query
            },
        )

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                with patch(
                    "api.v1.shopping_list.update_item.dispatch"
                ) as dispatch_mock:
                    response = client.put(
                        f"/v1/shopping-lists/{list_id}/items/{item_id}",
                        json={"is_checked": True},
                    )

        assert response.status_code == 200
        data = response.json()
        assert data["pantry_ingredient_id"] == ingredient_id
        assert data["pantry_id"] == str(pantry.id)
        assert dispatch_mock.called
        event_name, payload = dispatch_mock.call_args[0]
        assert event_name == "ShoppingListItemPurchased"
        assert str(payload.ingredient_id) == ingredient_id

    def test_check_without_ingredient_skips_hook(self, client, mock_db, mock_user):
        """Free-text items (no ingredient_id) do not trigger the pantry hook."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            is_checked=False,
            ingredient_id=None,
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListItem, item, id=item_id, shopping_list_id=list_id
        )
        mock_db.db.query.return_value = MockQuery([])

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                with patch(
                    "api.v1.shopping_list.update_item.dispatch"
                ) as dispatch_mock:
                    response = client.put(
                        f"/v1/shopping-lists/{list_id}/items/{item_id}",
                        json={"is_checked": True},
                    )

        assert response.status_code == 200
        data = response.json()
        assert data["pantry_ingredient_id"] is None
        assert data["pantry_id"] is None
        assert not dispatch_mock.called

    def test_uncheck_does_not_fire_hook(self, client, mock_db, mock_user):
        """Unchecking an already-checked item does not touch the pantry."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            is_checked=True,
            ingredient_id=ingredient_id,
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListItem, item, id=item_id, shopping_list_id=list_id
        )

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                with patch(
                    "api.v1.shopping_list.update_item.dispatch"
                ) as dispatch_mock:
                    response = client.put(
                        f"/v1/shopping-lists/{list_id}/items/{item_id}",
                        json={"is_checked": False},
                    )

        assert response.status_code == 200
        assert not dispatch_mock.called

    def test_pantry_hook_failure_does_not_break_request(
        self, client, mock_db, mock_user
    ):
        """A crash inside the pantry side-effect is swallowed."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            is_checked=False,
            ingredient_id=ingredient_id,
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListItem, item, id=item_id, shopping_list_id=list_id
        )
        mock_db.db.query.return_value = MockQuery([])

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                with patch(
                    "api.v1.shopping_list.update_item.get_or_create_default_pantry",
                    side_effect=RuntimeError("boom"),
                ):
                    response = client.put(
                        f"/v1/shopping-lists/{list_id}/items/{item_id}",
                        json={"is_checked": True},
                    )

        # Request still succeeds even though the hook blew up.
        assert response.status_code == 200
        data = response.json()
        assert data["is_checked"] is True
        assert data["pantry_ingredient_id"] is None
