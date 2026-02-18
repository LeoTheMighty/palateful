"""Tests for shopping list endpoints."""

from conftest import (
    MockQuery,
    MockShoppingList,
    MockShoppingListItem,
    MockShoppingListUser,
    MockUser,
)


class TestListShoppingLists:
    """Tests for GET /v1/shopping-lists."""

    def test_list_shopping_lists_success(self, client, mock_db, mock_user):
        """Test listing shopping lists."""
        sl = MockShoppingList(owner_id=str(mock_user.id))
        membership = MockShoppingListUser(
            shopping_list_id=str(sl.id),
            user_id=str(mock_user.id),
            role="owner",
        )
        mock_db.db.query.return_value = MockQuery([(sl, membership, 3)])

        response = client.get("/v1/shopping-lists")
        assert response.status_code == 200

    def test_list_shopping_lists_empty(self, client, mock_db, mock_user):
        """Test listing when user has no shopping lists."""
        mock_db.db.query.return_value = MockQuery([])

        response = client.get("/v1/shopping-lists")
        assert response.status_code == 200


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

    def test_create_shopping_list_missing_name(self, client, mock_db):
        """Test creating without name fails."""
        response = client.post(
            "/v1/shopping-lists",
            json={}
        )
        assert response.status_code == 422


class TestGetShoppingList:
    """Tests for GET /v1/shopping-lists/{list_id}."""

    def test_get_shopping_list_success(self, client, mock_db, mock_user):
        """Test getting a shopping list."""
        list_id = "test-list-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
        )

        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingListUser, membership,
                           user_id=str(mock_user.id),
                           shopping_list_id=list_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.get(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == list_id

    def test_get_shopping_list_no_access(self, client, mock_db, mock_user):
        """Test getting a shopping list without access."""
        response = client.get("/v1/shopping-lists/no-access")
        assert response.status_code in (403, 404, 500)


class TestDeleteShoppingList:
    """Tests for DELETE /v1/shopping-lists/{list_id}."""

    def test_delete_shopping_list_success(self, client, mock_db, mock_user):
        """Test deleting a shopping list as owner."""
        list_id = "test-list-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="owner",
        )

        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingListUser, membership,
                           user_id=str(mock_user.id),
                           shopping_list_id=list_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.delete(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 200


class TestAddShoppingListItem:
    """Tests for POST /v1/shopping-lists/{list_id}/items."""

    def test_add_item_success(self, client, mock_db, mock_user):
        """Test adding an item to a shopping list."""
        list_id = "test-list-id"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
        )

        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingListUser, membership,
                           user_id=str(mock_user.id),
                           shopping_list_id=list_id)
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
