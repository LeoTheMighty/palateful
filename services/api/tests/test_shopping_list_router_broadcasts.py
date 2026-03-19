"""Tests for real-time WebSocket broadcasts in shopping list router endpoints."""

from unittest.mock import AsyncMock, patch

from conftest import (
    MockShoppingList,
    MockShoppingListItem,
    MockShoppingListUser,
)


class TestAddItemBroadcast:
    """Verify broadcast_event_to_list is called when an item is added."""

    def test_add_item_broadcasts_item_added(self, client, mock_db, mock_user):
        """Adding an item triggers an item_added WebSocket broadcast."""
        list_id = "test-list-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            response = client.post(
                f"/v1/shopping-lists/{list_id}/items",
                json={"name": "Apples"},
            )

        assert response.status_code == 201
        mock_broadcast.assert_called_once()
        args = mock_broadcast.call_args[0]
        assert args[0] == list_id
        assert args[1] == "item_added"
        # item_data is the third arg — must be a dict with 'name'
        assert isinstance(args[2], dict)
        assert args[2]["name"] == "Apples"

    def test_add_item_broadcast_includes_user_id(self, client, mock_db, mock_user):
        """Broadcast carries the actor's user_id as kwarg."""
        list_id = "test-list-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            client.post(
                f"/v1/shopping-lists/{list_id}/items",
                json={"name": "Bread"},
            )

        assert mock_broadcast.called
        kwargs = mock_broadcast.call_args[1]
        assert kwargs.get("user_id") == str(mock_user.id)


class TestUpdateItemBroadcast:
    """Verify broadcast_event_to_list is called when an item is updated."""

    def test_update_item_broadcasts_item_updated(self, client, mock_db, mock_user):
        """Updating item name triggers 'item_updated' broadcast."""
        list_id = "test-list-id"
        item_id = "test-item-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Old Name")

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            response = client.put(
                f"/v1/shopping-lists/{list_id}/items/{item_id}",
                json={"name": "New Name"},
            )

        assert response.status_code == 200
        mock_broadcast.assert_called_once()
        assert mock_broadcast.call_args[0][1] == "item_updated"

    def test_update_item_is_checked_broadcasts_item_checked(self, client, mock_db, mock_user):
        """Checking an item triggers 'item_checked' broadcast."""
        list_id = "test-list-id"
        item_id = "test-item-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        # Mock for unchecked_count query
        from conftest import MockQuery
        mock_db.db.query.return_value = MockQuery([])

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            with patch("api.v1.shopping_list.update_item.notify_item_checked"):
                with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                    response = client.put(
                        f"/v1/shopping-lists/{list_id}/items/{item_id}",
                        json={"is_checked": True},
                    )

        assert response.status_code == 200
        mock_broadcast.assert_called_once()
        assert mock_broadcast.call_args[0][1] == "item_checked"


class TestDeleteItemBroadcast:
    """Verify broadcast_event_to_list is called when an item is deleted."""

    def test_delete_item_broadcasts_item_removed(self, client, mock_db, mock_user):
        """Deleting an item triggers 'item_removed' broadcast with item_id."""
        list_id = "test-list-id"
        item_id = "test-item-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id)

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            response = client.delete(
                f"/v1/shopping-lists/{list_id}/items/{item_id}",
            )

        assert response.status_code == 200
        mock_broadcast.assert_called_once()
        args = mock_broadcast.call_args[0]
        assert args[0] == list_id
        assert args[1] == "item_removed"
        assert args[2] == {"item_id": item_id}

    def test_delete_item_broadcast_carries_user_id(self, client, mock_db, mock_user):
        """Delete broadcast includes the actor's user_id."""
        list_id = "test-list-id"
        item_id = "test-item-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id)

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            client.delete(f"/v1/shopping-lists/{list_id}/items/{item_id}")

        assert mock_broadcast.called
        kwargs = mock_broadcast.call_args[1]
        assert kwargs.get("user_id") == str(mock_user.id)


class TestListShoppingListsUpdatedAt:
    """Verify ListShoppingLists response includes updated_at (Task 1)."""

    def test_list_returns_updated_at(self, client, mock_db, mock_user):
        """Each list item in the response includes an updated_at field."""
        sl = MockShoppingList(
            owner_id=str(mock_user.id),
            items=[],
            members=[],
        )
        from conftest import MockQuery
        mock_db.db.query.return_value = MockQuery([sl])

        response = client.get("/v1/shopping-lists")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert "updated_at" in items[0]
        assert items[0]["updated_at"] is not None
