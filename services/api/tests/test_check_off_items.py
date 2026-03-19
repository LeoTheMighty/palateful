"""Tests for UpdateShoppingListItem check-off path."""

import uuid
from unittest.mock import patch

from conftest import (
    MockQuery,
    MockShoppingList,
    MockShoppingListItem,
    MockShoppingListUser,
)


class TestCheckOffItemSuccess:
    """Core success path — check and uncheck an item."""

    def test_check_item_sets_is_checked_true(self, client, mock_db, mock_user):
        """Checking an item returns is_checked=True."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        mock_db.db.query.return_value = MockQuery([])  # stub the unchecked_count query

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                response = client.put(
                    f"/v1/shopping-lists/{list_id}/items/{item_id}",
                    json={"is_checked": True},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["is_checked"] is True

    def test_check_item_sets_checked_at_and_checked_by(self, client, mock_db, mock_user):
        """Checking an item sets checked_at timestamp and checked_by_user_id."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        mock_db.db.query.return_value = MockQuery([])

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                response = client.put(
                    f"/v1/shopping-lists/{list_id}/items/{item_id}",
                    json={"is_checked": True},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["checked_by_user_id"] == str(mock_user.id)
        assert data["checked_at"] is not None

    def test_uncheck_item_clears_checked_fields(self, client, mock_db, mock_user):
        """Unchecking an item clears checked_at and checked_by_user_id."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            is_checked=True,
            checked_by_user_id=str(mock_user.id),
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}",
            json={"is_checked": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_checked"] is False
        assert data["checked_at"] is None
        assert data["checked_by_user_id"] is None


class TestCheckOffItemErrors:
    """Error cases — 404 and 403 responses."""

    def test_check_item_404_list_not_found(self, client, mock_db, mock_user):
        """Returns 404 when shopping list is not found."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        # ShoppingList not configured → find_by returns None

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}",
            json={"is_checked": True},
        )

        assert response.status_code == 404

    def test_check_item_403_no_access(self, client, mock_db, mock_user):
        """Returns 403 when user has no list access."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())
        other_owner_id = str(uuid.uuid4())

        # List owned by someone else, user has no membership
        sl = MockShoppingList(id=list_id, owner_id=other_owner_id)

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # ShoppingListUser not configured → find_by returns None → 403

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}",
            json={"is_checked": True},
        )

        assert response.status_code == 403

    def test_check_item_404_item_not_found(self, client, mock_db, mock_user):
        """Returns 404 when item is not found."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # ShoppingListItem not configured → find_by returns None → 404

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}",
            json={"is_checked": True},
        )

        assert response.status_code == 404

    def test_check_archived_item_returns_404(self, client, mock_db, mock_user):
        """Returns 404 when item is archived."""
        from datetime import datetime, timezone

        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            archived_at=datetime.now(timezone.utc),
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}",
            json={"is_checked": True},
        )

        assert response.status_code == 404


class TestCheckOffNotifications:
    """Verify notification hooks are called on check events."""

    def test_notify_item_checked_is_called(self, client, mock_db, mock_user):
        """notify_item_checked is called when item is checked."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        mock_db.db.query.return_value = MockQuery([item])  # 1 unchecked → no complete

        with patch(
            "api.v1.shopping_list.update_item.notify_item_checked"
        ) as mock_notify:
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                client.put(
                    f"/v1/shopping-lists/{list_id}/items/{item_id}",
                    json={"is_checked": True},
                )

        mock_notify.assert_called_once()

    def test_notify_item_checked_not_called_on_uncheck(self, client, mock_db, mock_user):
        """notify_item_checked is NOT called when item is unchecked."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            is_checked=True,
            checked_by_user_id=str(mock_user.id),
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        with patch(
            "api.v1.shopping_list.update_item.notify_item_checked"
        ) as mock_notify:
            client.put(
                f"/v1/shopping-lists/{list_id}/items/{item_id}",
                json={"is_checked": False},
            )

        mock_notify.assert_not_called()

    def test_notify_list_complete_called_when_last_item_checked(
        self, client, mock_db, mock_user
    ):
        """notify_list_complete is called when the last unchecked item is checked."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        # unchecked_count = 0 → all items now checked
        mock_db.db.query.return_value = MockQuery([])

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch(
                "api.v1.shopping_list.update_item.notify_list_complete"
            ) as mock_complete:
                client.put(
                    f"/v1/shopping-lists/{list_id}/items/{item_id}",
                    json={"is_checked": True},
                )

        mock_complete.assert_called_once()

    def test_notify_list_complete_not_called_when_items_remain(
        self, client, mock_db, mock_user
    ):
        """notify_list_complete is NOT called when unchecked items still remain."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())
        other_item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)
        other_item = MockShoppingListItem(
            id=other_item_id, shopping_list_id=list_id, is_checked=False
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        # 1 unchecked item still remains
        mock_db.db.query.return_value = MockQuery([other_item])

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch(
                "api.v1.shopping_list.update_item.notify_list_complete"
            ) as mock_complete:
                client.put(
                    f"/v1/shopping-lists/{list_id}/items/{item_id}",
                    json={"is_checked": True},
                )

        mock_complete.assert_not_called()

    def test_uncheck_broadcasts_item_checked_event(self, client, mock_db, mock_user):
        """Unchecking an item also fires 'item_checked' broadcast (not 'item_updated').

        The router uses `if params.is_checked is not None` → 'item_checked' for both
        check and uncheck. This test verifies the uncheck path uses the correct event type.
        """
        from unittest.mock import AsyncMock, patch

        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id,
            shopping_list_id=list_id,
            is_checked=True,
            checked_by_user_id=str(mock_user.id),
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list",
            new_callable=AsyncMock,
        ) as mock_broadcast:
            response = client.put(
                f"/v1/shopping-lists/{list_id}/items/{item_id}",
                json={"is_checked": False},
            )

        assert response.status_code == 200
        mock_broadcast.assert_called_once()
        assert mock_broadcast.call_args[0][1] == "item_checked", (
            "Uncheck should broadcast 'item_checked', not 'item_updated'"
        )
        assert response.json()["is_checked"] is False

    def test_editor_member_can_check_off_item(self, client, mock_db, mock_user):
        """A non-owner member with 'editor' role can check off items."""
        list_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())
        other_owner_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=other_owner_id)
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)
        editor_membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser,
            editor_membership,
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
        )
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        mock_db.db.query.return_value = MockQuery([])

        with patch("api.v1.shopping_list.update_item.notify_item_checked"):
            with patch("api.v1.shopping_list.update_item.notify_list_complete"):
                response = client.put(
                    f"/v1/shopping-lists/{list_id}/items/{item_id}",
                    json={"is_checked": True},
                )

        assert response.status_code == 200
        assert response.json()["is_checked"] is True
