"""Tests for shopping list endpoints."""

from unittest.mock import patch

from conftest import (
    MockQuery,
    MockShoppingList,
    MockShoppingListUser,
)


class TestListShoppingLists:
    """Tests for GET /v1/shopping-lists."""

    def test_list_shopping_lists_success(self, client, mock_db, mock_user):
        """Test listing shopping lists."""
        sl = MockShoppingList(
            owner_id=str(mock_user.id),
            items=[],
            members=[],
            is_shared=False,
        )
        # ListShoppingLists uses db.query(ShoppingList).filter(...)
        # The subquery for member_list_ids also uses db.query
        mock_db.db.query.return_value = MockQuery([sl])

        response = client.get("/v1/shopping-lists")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_list_shopping_lists_empty(self, client, mock_db, mock_user):
        """Test listing when user has no shopping lists."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/shopping-lists")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


class TestCreateShoppingList:
    """Tests for POST /v1/shopping-lists."""

    def test_create_shopping_list_success(self, client, mock_db, mock_user):
        """Test creating a shopping list."""
        response = client.post(
            "/v1/shopping-lists",
            json={"name": "Weekly Groceries"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Weekly Groceries"

    def test_create_shopping_list_no_name(self, client, mock_db, mock_user):
        """Test creating a shopping list with no name (allowed, name is optional)."""
        response = client.post(
            "/v1/shopping-lists",
            json={}
        )
        # CreateShoppingList.Params has name: str | None = None, so empty body is valid
        assert response.status_code == 201


class TestGetShoppingList:
    """Tests for GET /v1/shopping-lists/{list_id}."""

    def test_get_shopping_list_success(self, client, mock_db, mock_user):
        """Test getting a shopping list."""
        list_id = "test-list-id"
        sl = MockShoppingList(
            id=list_id,
            owner_id=str(mock_user.id),
            items=[],
            members=[],
            is_shared=False,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == list_id

    def test_get_shopping_list_no_access(self, client, mock_db, mock_user):
        """Test getting a shopping list without access."""
        response = client.get("/v1/shopping-lists/no-access")
        assert response.status_code == 404


class TestDeleteShoppingList:
    """Tests for DELETE /v1/shopping-lists/{list_id}."""

    def test_delete_shopping_list_success(self, client, mock_db, mock_user):
        """Test deleting a shopping list as owner."""
        list_id = "test-list-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.delete(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 200

    def test_delete_shopping_list_not_found(self, client, mock_db, mock_user):
        """Test deleting a nonexistent shopping list."""
        response = client.delete("/v1/shopping-lists/nonexistent")
        assert response.status_code == 404


class TestAddShoppingListItem:
    """Tests for POST /v1/shopping-lists/{list_id}/items."""

    @patch("api.v1.shopping_list.add_item.notify_item_added")
    def test_add_item_success(self, mock_notify, client, mock_db, mock_user):
        """Test adding an item to a shopping list."""
        list_id = "test-list-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/items",
            json={
                "name": "Milk",
                "quantity": 1,
                "unit": "gallon",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Milk"
