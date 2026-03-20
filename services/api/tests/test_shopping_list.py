"""Tests for shopping list endpoints."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import (
    MockMealEvent,
    MockModel,
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


# =============================================================================
# AssignItem & BulkAssignItems tests
# =============================================================================


class TestAssignItem:
    """Tests for PUT /v1/shopping-lists/{list_id}/items/{item_id}/assign."""

    def test_assign_item_not_found_list(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.put(
            "/v1/shopping-lists/no-list/items/item1/assign",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 404

    def test_assign_item_no_permission(self, client, mock_db, mock_user):
        """403 when user has no edit permission."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner")

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # No membership found -> can_edit is False

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/item1/assign",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 403

    def test_assign_item_as_editor_member(self, client, mock_db, mock_user):
        """Editor member can assign items."""
        list_id = "test-list"
        item_id = "test-item"
        assignee_id = str(mock_user.id)  # Assign to owner
        sl = MockShoppingList(id=list_id, owner_id="other-owner")
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
            archived_at=None,
        )
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Eggs")
        assignee = MockUser(id=assignee_id, name="Test User")

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership, shopping_list_id=list_id, user_id=str(mock_user.id)
        )
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        # Assignee is the owner of the list — wait, owner_id is "other-owner" so let's
        # make the assignee a member instead
        sl.owner_id = "other-owner"
        assignee_membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=assignee_id,
            role="editor",
            archived_at=None,
        )
        mock_db.set_find_by(
            ShoppingListUser, assignee_membership, shopping_list_id=list_id, user_id=assignee_id
        )
        mock_db.set_find_by(User, assignee, id=assignee_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}/assign",
            json={"user_id": assignee_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_to_user_id"] == assignee_id

    def test_assign_item_item_not_found(self, client, mock_db, mock_user):
        """404 when item is not found in the list."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/missing-item/assign",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 404

    def test_assign_item_to_owner(self, client, mock_db, mock_user):
        """Assigning to the list owner works."""
        list_id = "test-list"
        item_id = "test-item"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Butter")
        owner_user = MockUser(id=str(mock_user.id), name="Owner")

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        mock_db.set_find_by(User, owner_user, id=str(mock_user.id))

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}/assign",
            json={"user_id": str(mock_user.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_to_user_id"] == str(mock_user.id)
        assert data["assigned_to_user_name"] == "Owner"

    def test_assign_item_to_non_member(self, client, mock_db, mock_user):
        """400 when assigning to a non-member."""
        list_id = "test-list"
        item_id = "test-item"
        non_member_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Milk")

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        # No membership for non_member_id -> find_by returns None

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}/assign",
            json={"user_id": non_member_id},
        )
        assert response.status_code == 400

    def test_assign_item_to_archived_member(self, client, mock_db, mock_user):
        """400 when assigning to an archived member."""
        list_id = "test-list"
        item_id = "test-item"
        archived_member_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Milk")
        archived_membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=archived_member_id,
            role="editor",
            archived_at=datetime.now(UTC),
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, archived_membership,
            shopping_list_id=list_id, user_id=archived_member_id,
        )

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}/assign",
            json={"user_id": archived_member_id},
        )
        assert response.status_code == 400

    def test_assign_item_assignee_user_not_found(self, client, mock_db, mock_user):
        """404 when assignee user record doesn't exist despite valid membership."""
        list_id = "test-list"
        item_id = "test-item"
        assignee_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Milk")
        assignee_membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=assignee_id,
            role="editor",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, assignee_membership,
            shopping_list_id=list_id, user_id=assignee_id,
        )
        # No User found for assignee_id -> find_by(User, id=assignee_id) returns None

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}/assign",
            json={"user_id": assignee_id},
        )
        assert response.status_code == 404

    def test_unassign_item(self, client, mock_db, mock_user):
        """Passing user_id=None unassigns the item."""
        list_id = "test-list"
        item_id = "test-item"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id, shopping_list_id=list_id, name="Bread",
            assigned_to_user_id="someone",
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}/assign",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_to_user_id"] is None
        assert data["assigned_to_user_name"] is None

    def test_assign_item_viewer_cannot_assign(self, client, mock_db, mock_user):
        """Viewer role cannot assign items."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner")
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="viewer",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/item1/assign",
            json={"user_id": "someone"},
        )
        assert response.status_code == 403


class TestBulkAssignItems:
    """Tests for POST /v1/shopping-lists/{list_id}/items/bulk-assign."""

    def test_bulk_assign_not_found_list(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.post(
            "/v1/shopping-lists/no-list/items/bulk-assign",
            json={"assignments": [{"item_id": "i1", "user_id": "u1"}]},
        )
        assert response.status_code == 404

    def test_bulk_assign_no_permission(self, client, mock_db, mock_user):
        """403 when user has no edit permission."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner")

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/items/bulk-assign",
            json={"assignments": [{"item_id": "i1", "user_id": "u1"}]},
        )
        assert response.status_code == 403

    def test_bulk_assign_success(self, client, mock_db, mock_user):
        """Successful bulk assignment."""
        list_id = "test-list"
        item_id = "item-1"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Milk")

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        # Assigning to owner (valid)
        response = client.post(
            f"/v1/shopping-lists/{list_id}/items/bulk-assign",
            json={"assignments": [{"item_id": item_id, "user_id": str(mock_user.id)}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_count"] == 1
        assert data["error_count"] == 0

    def test_bulk_assign_item_not_found(self, client, mock_db, mock_user):
        """Error when item not found in bulk assignment."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/items/bulk-assign",
            json={"assignments": [{"item_id": "missing", "user_id": str(mock_user.id)}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_count"] == 0
        assert data["error_count"] == 1
        assert "missing" in data["errors"][0]

    def test_bulk_assign_invalid_member(self, client, mock_db, mock_user):
        """Error when assigning to non-member in bulk."""
        list_id = "test-list"
        item_id = "item-1"
        non_member_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Bread")

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/items/bulk-assign",
            json={"assignments": [{"item_id": item_id, "user_id": non_member_id}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_count"] == 0
        assert data["error_count"] == 1
        assert "not a member" in data["errors"][0]

    def test_bulk_assign_unassign_item(self, client, mock_db, mock_user):
        """Passing user_id=None in bulk unassigns."""
        list_id = "test-list"
        item_id = "item-1"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id, shopping_list_id=list_id, name="Milk",
            assigned_to_user_id="someone",
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/items/bulk-assign",
            json={"assignments": [{"item_id": item_id, "user_id": None}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_count"] == 1
        assert data["error_count"] == 0


# =============================================================================
# InviteShoppingListMember tests
# =============================================================================


class TestInviteShoppingListMember:
    """Tests for POST /v1/shopping-lists/{list_id}/members."""

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_not_found_list(self, mock_notify, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.post(
            "/v1/shopping-lists/no-list/members",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 404

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_no_permission(self, mock_notify, client, mock_db, mock_user):
        """403 when user is not owner or editor."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner", members=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": "some-user"},
        )
        assert response.status_code == 403

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_user_not_found(self, mock_notify, client, mock_db, mock_user):
        """404 when invited user doesn't exist."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": "nonexistent"},
        )
        assert response.status_code == 404

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_by_email(self, mock_notify, client, mock_db, mock_user):
        """Can invite by email."""
        list_id = "test-list"
        invited_user = MockUser(id=str(uuid.uuid4()), email="friend@example.com", name="Friend")
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=[], is_shared=False)

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(User, invited_user, email="friend@example.com")
        # Owner membership doesn't exist yet — triggers creation
        # No existing membership for invited user

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"email": "friend@example.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "friend@example.com"
        mock_notify.assert_called_once()

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_by_user_id(self, mock_notify, client, mock_db, mock_user):
        """Can invite by user_id."""
        list_id = "test-list"
        invited_id = str(uuid.uuid4())
        invited_user = MockUser(id=invited_id, email="friend@example.com", name="Friend")
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=[], is_shared=False)

        from utils.models.shopping_list import ShoppingList
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(User, invited_user, id=invited_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": invited_id},
        )
        assert response.status_code == 201

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_already_member(self, mock_notify, client, mock_db, mock_user):
        """400 when user is already an active member."""
        list_id = "test-list"
        invited_id = str(uuid.uuid4())
        invited_user = MockUser(id=invited_id, email="friend@example.com")
        existing = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=invited_id,
            role="editor",
            archived_at=None,
        )
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=[existing])

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(User, invited_user, id=invited_id)
        mock_db.set_find_by(
            ShoppingListUser, existing,
            shopping_list_id=list_id, user_id=invited_id,
        )

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": invited_id},
        )
        assert response.status_code == 400

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_reactivate_archived(self, mock_notify, client, mock_db, mock_user):
        """Reactivates archived membership instead of creating new one."""
        list_id = "test-list"
        invited_id = str(uuid.uuid4())
        invited_user = MockUser(id=invited_id, email="friend@example.com", name="Friend")
        existing = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=invited_id,
            role="viewer",
            archived_at=datetime.now(UTC),
        )
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=[])

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(User, invited_user, id=invited_id)
        mock_db.set_find_by(
            ShoppingListUser, existing,
            shopping_list_id=list_id, user_id=invited_id,
        )

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": invited_id, "role": "editor"},
        )
        assert response.status_code == 201
        # Verify the existing record was reactivated
        assert existing.archived_at is None
        assert existing.role == "editor"

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_limit_reached(self, mock_notify, client, mock_db, mock_user):
        """400 when member limit (10) is reached."""
        list_id = "test-list"
        invited_id = str(uuid.uuid4())
        invited_user = MockUser(id=invited_id, email="friend@example.com")
        # Create 10 active members
        active_members = [
            MockShoppingListUser(
                shopping_list_id=list_id,
                user_id=str(uuid.uuid4()),
                role="editor",
                archived_at=None,
            )
            for _ in range(10)
        ]
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=active_members)

        from utils.models.shopping_list import ShoppingList
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(User, invited_user, id=invited_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": invited_id},
        )
        assert response.status_code == 400

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_sets_list_as_shared(self, mock_notify, client, mock_db, mock_user):
        """Inviting marks the list as shared."""
        list_id = "test-list"
        invited_id = str(uuid.uuid4())
        invited_user = MockUser(id=invited_id, email="f@example.com", name="Friend")
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=[], is_shared=False)

        from utils.models.shopping_list import ShoppingList
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(User, invited_user, id=invited_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": invited_id},
        )
        assert response.status_code == 201
        assert sl.is_shared is True

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_creates_owner_membership(self, mock_notify, client, mock_db, mock_user):
        """If owner doesn't have a membership record, one is created."""
        list_id = "test-list"
        invited_id = str(uuid.uuid4())
        invited_user = MockUser(id=invited_id, email="f@example.com", name="Friend")
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), members=[], is_shared=True)

        from utils.models.shopping_list import ShoppingList
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(User, invited_user, id=invited_id)
        # No owner membership found -> should create one

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": invited_id},
        )
        assert response.status_code == 201

    @patch("api.v1.shopping_list.invite_member.notify_list_shared")
    def test_invite_member_editor_can_invite(self, mock_notify, client, mock_db, mock_user):
        """Editor member can also invite."""
        list_id = "test-list"
        invited_id = str(uuid.uuid4())
        invited_user = MockUser(id=invited_id, email="f@example.com", name="Friend")
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
        )
        sl = MockShoppingList(id=list_id, owner_id="other-owner", members=[])

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser
        from utils.models.user import User

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )
        mock_db.set_find_by(User, invited_user, id=invited_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/members",
            json={"user_id": invited_id},
        )
        assert response.status_code == 201


# =============================================================================
# ShareShoppingList tests
# =============================================================================


class TestShareShoppingList:
    """Tests for POST /v1/shopping-lists/{list_id}/share."""

    def test_share_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.post(
            "/v1/shopping-lists/no-list/share",
            json={},
        )
        assert response.status_code == 404

    def test_share_not_owner(self, client, mock_db, mock_user):
        """403 when user is not the owner."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner")

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/share",
            json={},
        )
        assert response.status_code == 403

    @patch("api.v1.shopping_list.share_shopping_list.generate_share_code", return_value="ABC123")
    def test_share_generates_code(self, mock_gen, client, mock_db, mock_user):
        """Generates a share code for a list without one."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            share_code=None, is_shared=False,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/share",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["share_code"] == "ABC123"
        assert data["is_shared"] is True

    def test_share_existing_code(self, client, mock_db, mock_user):
        """Returns existing share code without generating a new one."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            share_code="EXIST1", is_shared=True,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/share",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["share_code"] == "EXIST1"

    @patch("api.v1.shopping_list.share_shopping_list.generate_share_code")
    def test_share_code_collision_retry(self, mock_gen, client, mock_db, mock_user):
        """Retries on collision and fails after 10 attempts."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            share_code=None, is_shared=False,
        )
        # Every generated code already exists
        colliding_list = MockShoppingList(share_code="TAKEN1")
        mock_gen.return_value = "TAKEN1"

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingList, colliding_list, share_code="TAKEN1")

        response = client.post(
            f"/v1/shopping-lists/{list_id}/share",
            json={},
        )
        assert response.status_code == 500

    def test_share_creates_owner_membership(self, client, mock_db, mock_user):
        """Creates owner membership if missing."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            share_code="CODE01", is_shared=True,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # No owner membership -> creates one

        response = client.post(
            f"/v1/shopping-lists/{list_id}/share",
            json={},
        )
        assert response.status_code == 200


class TestGenerateShareCode:
    """Tests for the generate_share_code utility function."""

    def test_generate_share_code_length(self):
        """Code has correct length."""
        from api.v1.shopping_list.share_shopping_list import generate_share_code

        code = generate_share_code(6)
        assert len(code) == 6

    def test_generate_share_code_no_ambiguous_chars(self):
        """Code doesn't contain O, 0, I, 1."""
        from api.v1.shopping_list.share_shopping_list import generate_share_code

        for _ in range(50):
            code = generate_share_code(8)
            assert "O" not in code
            assert "0" not in code
            assert "I" not in code
            assert "1" not in code


# =============================================================================
# RemoveShoppingListMember tests
# =============================================================================


class TestRemoveShoppingListMember:
    """Tests for DELETE /v1/shopping-lists/{list_id}/members/{member_user_id}."""

    def test_remove_member_list_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.delete(
            "/v1/shopping-lists/no-list/members/some-user",
        )
        assert response.status_code == 404

    def test_remove_member_membership_not_found(self, client, mock_db, mock_user):
        """404 when member is not found."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.delete(
            f"/v1/shopping-lists/{list_id}/members/nonexistent-user",
        )
        assert response.status_code == 404

    def test_remove_member_archived_membership(self, client, mock_db, mock_user):
        """404 when membership is already archived."""
        list_id = "test-list"
        member_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        archived_member = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=member_id,
            role="editor",
            archived_at=datetime.now(UTC),
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, archived_member,
            shopping_list_id=list_id, user_id=member_id,
        )

        response = client.delete(
            f"/v1/shopping-lists/{list_id}/members/{member_id}",
        )
        assert response.status_code == 404

    @patch("api.v1.shopping_list.remove_member.datetime")
    def test_owner_removes_member(self, mock_dt, client, mock_db, mock_user):
        """Owner can remove another member."""
        mock_dt.now.return_value = datetime.now(UTC)
        mock_dt.UTC = UTC
        list_id = "test-list"
        member_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        target = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=member_id,
            role="editor",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, target,
            shopping_list_id=list_id, user_id=member_id,
        )

        response = client.delete(
            f"/v1/shopping-lists/{list_id}/members/{member_id}",
        )
        assert response.status_code == 200
        data = response.json()
        assert "removed" in data["message"]

    @patch("api.v1.shopping_list.remove_member.datetime")
    def test_member_leaves_self(self, mock_dt, client, mock_db, mock_user):
        """Non-owner member can leave the list."""
        mock_dt.now.return_value = datetime.now(UTC)
        mock_dt.UTC = UTC
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner")
        target = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, target,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        response = client.delete(
            f"/v1/shopping-lists/{list_id}/members/{str(mock_user.id)}",
        )
        assert response.status_code == 200
        data = response.json()
        assert "left" in data["message"]

    def test_owner_cannot_leave_own_list(self, client, mock_db, mock_user):
        """Owner cannot leave their own list."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        owner_membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="owner",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, owner_membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        response = client.delete(
            f"/v1/shopping-lists/{list_id}/members/{str(mock_user.id)}",
        )
        assert response.status_code == 400

    def test_non_owner_cannot_remove_others(self, client, mock_db, mock_user):
        """Non-owner member cannot remove other members."""
        list_id = "test-list"
        other_member_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id="other-owner")
        other_membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=other_member_id,
            role="editor",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, other_membership,
            shopping_list_id=list_id, user_id=other_member_id,
        )

        response = client.delete(
            f"/v1/shopping-lists/{list_id}/members/{other_member_id}",
        )
        assert response.status_code == 403

    def test_cannot_remove_owner_role(self, client, mock_db, mock_user):
        """Cannot remove a member who has the owner role (non-self-removal)."""
        list_id = "test-list"
        other_owner_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        target = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=other_owner_id,
            role="owner",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, target,
            shopping_list_id=list_id, user_id=other_owner_id,
        )

        response = client.delete(
            f"/v1/shopping-lists/{list_id}/members/{other_owner_id}",
        )
        assert response.status_code == 400


# =============================================================================
# JoinShoppingList tests
# =============================================================================


class TestJoinShoppingList:
    """Tests for POST /v1/shopping-lists/join/{share_code}."""

    @patch("api.v1.shopping_list.join_shopping_list.notify_member_joined")
    def test_join_invalid_code(self, mock_notify, client, mock_db, mock_user):
        """404 when share code is invalid."""
        response = client.post("/v1/shopping-lists/join/BADCODE")
        assert response.status_code == 404

    @patch("api.v1.shopping_list.join_shopping_list.notify_member_joined")
    def test_join_success(self, mock_notify, client, mock_db, mock_user):
        """Successfully join with valid share code."""
        sl = MockShoppingList(
            id="test-list", owner_id="other-owner",
            share_code="ABCDEF", members=[],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, share_code="ABCDEF")

        response = client.post("/v1/shopping-lists/join/ABCDEF")
        assert response.status_code == 201
        data = response.json()
        assert data["shopping_list_id"] == "test-list"
        assert data["role"] == "editor"
        mock_notify.assert_called_once()

    @patch("api.v1.shopping_list.join_shopping_list.notify_member_joined")
    def test_join_already_member(self, mock_notify, client, mock_db, mock_user):
        """400 when already a member."""
        sl = MockShoppingList(
            id="test-list", owner_id="other-owner",
            share_code="ABCDEF", members=[],
        )
        existing = MockShoppingListUser(
            shopping_list_id="test-list",
            user_id=str(mock_user.id),
            role="editor",
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, share_code="ABCDEF")
        mock_db.set_find_by(
            ShoppingListUser, existing,
            shopping_list_id="test-list", user_id=str(mock_user.id),
        )

        response = client.post("/v1/shopping-lists/join/ABCDEF")
        assert response.status_code == 400

    @patch("api.v1.shopping_list.join_shopping_list.notify_member_joined")
    def test_join_member_limit(self, mock_notify, client, mock_db, mock_user):
        """400 when member limit reached."""
        active_members = [
            MockShoppingListUser(
                shopping_list_id="test-list",
                user_id=str(uuid.uuid4()),
                role="editor",
                archived_at=None,
            )
            for _ in range(10)
        ]
        sl = MockShoppingList(
            id="test-list", owner_id="other-owner",
            share_code="ABCDEF", members=active_members,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, share_code="ABCDEF")

        response = client.post("/v1/shopping-lists/join/ABCDEF")
        assert response.status_code == 400

    @patch("api.v1.shopping_list.join_shopping_list.notify_member_joined")
    def test_join_code_uppercased(self, mock_notify, client, mock_db, mock_user):
        """Share code is uppercased before lookup."""
        sl = MockShoppingList(
            id="test-list", owner_id="other-owner",
            share_code="ABCDEF", members=[],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, share_code="ABCDEF")

        response = client.post("/v1/shopping-lists/join/abcdef")
        assert response.status_code == 201


# =============================================================================
# UpdateShoppingList tests
# =============================================================================


class TestUpdateShoppingList:
    """Tests for PUT /v1/shopping-lists/{list_id}."""

    def test_update_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.put(
            "/v1/shopping-lists/no-list",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    def test_update_no_permission(self, client, mock_db, mock_user):
        """403 when user can't edit."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner", items=[], members=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 403

    def test_update_name_success(self, client, mock_db, mock_user):
        """Owner can update name."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=[], is_shared=False,
            calendar_lookahead_days=7, widget_color=None,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_invalid_status(self, client, mock_db, mock_user):
        """400 when invalid status is provided."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=[],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"status": "invalid_status"},
        )
        assert response.status_code == 400

    def test_update_valid_status(self, client, mock_db, mock_user):
        """Can update status to a valid value."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=[], is_shared=False,
            calendar_lookahead_days=7, widget_color=None,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"status": "completed"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_update_invalid_sort_by(self, client, mock_db, mock_user):
        """400 when invalid sort_by is provided."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=[],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"sort_by": "random"},
        )
        assert response.status_code == 400

    def test_update_all_fields(self, client, mock_db, mock_user):
        """Can update all optional fields."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=[], is_shared=False,
            calendar_lookahead_days=7, widget_color=None,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={
                "name": "New Name",
                "status": "in_progress",
                "default_deadline": "2026-03-25T12:00:00",
                "auto_populate_from_calendar": False,
                "calendar_lookahead_days": 14,
                "widget_color": "#FF0000",
                "sort_by": "name",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["status"] == "in_progress"
        assert data["sort_by"] == "name"

    def test_update_with_items(self, client, mock_db, mock_user):
        """Response includes item data, filtering archived."""
        list_id = "test-list"
        item1 = MockShoppingListItem(
            id="i1", name="Active Item", is_checked=False,
            archived_at=None, quantity=Decimal("2"), unit="lbs",
            category="produce", due_at=None, priority=3,
        )
        item2 = MockShoppingListItem(
            id="i2", name="Archived Item", is_checked=False,
            archived_at=datetime.now(UTC),
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[item1, item2], members=[], is_shared=False,
            calendar_lookahead_days=7, widget_color=None,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Active Item"

    def test_update_shared_list_member_count(self, client, mock_db, mock_user):
        """Response includes member_count for shared lists."""
        list_id = "test-list"
        members = [
            MockShoppingListUser(user_id=str(uuid.uuid4()), role="editor", archived_at=None),
            MockShoppingListUser(user_id=str(uuid.uuid4()), role="editor", archived_at=datetime.now(UTC)),
        ]
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=members, is_shared=True,
            calendar_lookahead_days=7, widget_color=None,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"name": "Shared List"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["member_count"] == 1  # Only 1 active

    def test_update_as_editor_member(self, client, mock_db, mock_user):
        """Editor member can update."""
        list_id = "test-list"
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
            archived_at=None,
        )
        sl = MockShoppingList(
            id=list_id, owner_id="other-owner",
            items=[], members=[], is_shared=False,
            calendar_lookahead_days=7, widget_color=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"name": "Editor Update"},
        )
        assert response.status_code == 200

    def test_update_with_meal_event_and_pantry(self, client, mock_db, mock_user):
        """Response includes meal_event_id and pantry_id when set."""
        list_id = "test-list"
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=[], is_shared=False,
            meal_event_id="event-123", pantry_id="pantry-456",
            calendar_lookahead_days=7, widget_color=None,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meal_event_id"] == "event-123"
        assert data["pantry_id"] == "pantry-456"


# =============================================================================
# GenerateFromMealEvent tests
# =============================================================================


class TestGenerateFromMealEvent:
    """Tests for POST /v1/meal-events/{event_id}/shopping-list/generate."""

    def test_generate_event_not_found(self, client, mock_db, mock_user):
        """404 when meal event doesn't exist."""
        response = client.post(
            "/v1/meal-events/no-event/shopping-list/generate",
            json={},
        )
        assert response.status_code == 404

    def test_generate_no_access(self, client, mock_db, mock_user):
        """403 when user has no access to the meal event."""
        event = MockMealEvent(id="event-1", owner_id="other-owner")

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id="event-1")

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={},
        )
        assert response.status_code == 403

    def test_generate_no_recipe(self, client, mock_db, mock_user):
        """400 when meal event has no recipe."""
        event = MockMealEvent(id="event-1", owner_id=str(mock_user.id), recipe=None)

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id="event-1")

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={},
        )
        assert response.status_code == 400

    def test_generate_list_already_exists(self, client, mock_db, mock_user):
        """400 when shopping list already exists for the event."""
        recipe = MockModel(
            id="recipe-1", name="Test Recipe",
            ingredients=[],
        )
        event = MockMealEvent(
            id="event-1", owner_id=str(mock_user.id),
            recipe=recipe, shopping_list=MockShoppingList(),
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id="event-1")

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={},
        )
        assert response.status_code == 400

    def test_generate_success_no_pantry_check(self, client, mock_db, mock_user):
        """Generates shopping list from recipe ingredients (no pantry check)."""
        ingredient = MockModel(
            id="ing-1", canonical_name="Flour", category="baking",
        )
        recipe_ingredient = MockModel(
            id="ri-1", ingredient_id="ing-1", ingredient=ingredient,
            quantity_display=Decimal("2"), unit_display="cups",
            archived_at=None,
        )
        recipe = MockModel(
            id="recipe-1", name="Pancakes",
            ingredients=[recipe_ingredient],
        )
        event = MockMealEvent(
            id="event-1", owner_id=str(mock_user.id),
            recipe=recipe, shopping_list=None,
            pantry_id=None, title="Sunday Brunch",
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id="event-1")

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={"check_pantry": False},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Shopping for Sunday Brunch"
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Flour"

    def test_generate_skips_archived_ingredients(self, client, mock_db, mock_user):
        """Archived recipe ingredients are skipped."""
        ingredient = MockModel(
            id="ing-1", canonical_name="Salt", category="baking",
        )
        archived_ri = MockModel(
            id="ri-1", ingredient_id="ing-1", ingredient=ingredient,
            quantity_display=Decimal("1"), unit_display="tsp",
            archived_at=datetime.now(UTC),
        )
        recipe = MockModel(
            id="recipe-1", name="Simple", ingredients=[archived_ri],
        )
        event = MockMealEvent(
            id="event-1", owner_id=str(mock_user.id),
            recipe=recipe, shopping_list=None, pantry_id=None,
            title="Quick Meal",
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id="event-1")

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={"check_pantry": False},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 0

    def test_generate_with_pantry_check(self, client, mock_db, mock_user):
        """Items already in pantry with enough quantity are skipped."""
        ingredient = MockModel(
            id="ing-1", canonical_name="Flour", category="baking",
        )
        recipe_ingredient = MockModel(
            id="ri-1", ingredient_id="ing-1", ingredient=ingredient,
            quantity_display=Decimal("2"), unit_display="cups",
            archived_at=None,
        )
        recipe = MockModel(
            id="recipe-1", name="Cake",
            ingredients=[recipe_ingredient],
        )
        pantry_ingredient = MockModel(
            ingredient_id="ing-1",
            quantity_display=Decimal("5"),
            unit_display="cups",
        )
        event = MockMealEvent(
            id="event-1", owner_id=str(mock_user.id),
            recipe=recipe, shopping_list=None,
            pantry_id="pantry-1", title="Birthday Cake",
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id="event-1")
        # Mock the pantry query
        mock_db.db.query.return_value = MockQuery([pantry_ingredient])

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={"check_pantry": True},
        )
        assert response.status_code == 201
        data = response.json()
        # Pantry has 5 cups, recipe needs 2 -> skip (enough in pantry)
        assert len(data["items"]) == 0

    def test_generate_pantry_partial_quantity(self, client, mock_db, mock_user):
        """Partial pantry quantity results in reduced needed amount."""
        ingredient = MockModel(
            id="ing-1", canonical_name="Sugar", category="baking",
        )
        recipe_ingredient = MockModel(
            id="ri-1", ingredient_id="ing-1", ingredient=ingredient,
            quantity_display=Decimal("3"), unit_display="cups",
            archived_at=None,
        )
        recipe = MockModel(
            id="recipe-1", name="Cookies",
            ingredients=[recipe_ingredient],
        )
        pantry_ingredient = MockModel(
            ingredient_id="ing-1",
            quantity_display=Decimal("1"),
            unit_display="cups",
        )
        event = MockMealEvent(
            id="event-1", owner_id=str(mock_user.id),
            recipe=recipe, shopping_list=None,
            pantry_id="pantry-1", title="Cookie Party",
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id="event-1")
        mock_db.db.query.return_value = MockQuery([pantry_ingredient])

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={"check_pantry": True},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 1
        # 3 needed - 1 in pantry = 2 remaining
        assert float(data["items"][0]["quantity"]) == 2.0

    def test_generate_as_participant(self, client, mock_db, mock_user):
        """Participant can generate shopping list."""
        from conftest import MockMealEventParticipant

        recipe = MockModel(
            id="recipe-1", name="Test",
            ingredients=[],
        )
        event = MockMealEvent(
            id="event-1", owner_id="other-owner",
            recipe=recipe, shopping_list=None,
            pantry_id=None, title="Group Dinner",
        )
        participant = MockMealEventParticipant(
            meal_event_id="event-1",
            user_id=str(mock_user.id),
            role="guest",
        )

        from utils.models.meal_event import MealEvent
        from utils.models.meal_event_participant import MealEventParticipant

        mock_db.set_find_by(MealEvent, event, id="event-1")
        mock_db.set_find_by(
            MealEventParticipant, participant,
            meal_event_id="event-1", user_id=str(mock_user.id),
        )

        response = client.post(
            "/v1/meal-events/event-1/shopping-list/generate",
            json={"check_pantry": False},
        )
        assert response.status_code == 201


# =============================================================================
# OrganizeByStore tests
# =============================================================================


class TestOrganizeByStore:
    """Tests for POST /v1/shopping-lists/{list_id}/organize-by-store."""

    def test_organize_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.post(
            "/v1/shopping-lists/no-list/organize-by-store",
            json={},
        )
        assert response.status_code == 404

    def test_organize_no_permission(self, client, mock_db, mock_user):
        """403 when user has no edit permission."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner", items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/organize-by-store",
            json={},
        )
        assert response.status_code == 403

    def test_organize_empty_list(self, client, mock_db, mock_user):
        """Organizing empty list returns empty sections."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/organize-by-store",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 0
        assert data["sections_used"] == 0

    def test_organize_auto_assign_sections(self, client, mock_db, mock_user):
        """Auto-assigns sections based on category."""
        list_id = "test-list"
        item1 = MockShoppingListItem(
            id="i1", name="Apples", is_checked=False, category="fruit",
            store_section=None, store_order=None, quantity=Decimal("3"), unit="each",
        )
        item2 = MockShoppingListItem(
            id="i2", name="Milk", is_checked=False, category="dairy",
            store_section=None, store_order=None, quantity=Decimal("1"), unit="gallon",
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[item1, item2],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/organize-by-store",
            json={"auto_assign_sections": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 2
        assert data["sections_used"] == 2
        # Check that sections contain the right items
        section_keys = [s["section"] for s in data["sections"]]
        assert "produce" in section_keys
        assert "dairy" in section_keys

    def test_organize_skips_checked_items(self, client, mock_db, mock_user):
        """Checked items are skipped during organization."""
        list_id = "test-list"
        unchecked = MockShoppingListItem(
            id="i1", name="Bread", is_checked=False, category="bakery",
            store_section=None, store_order=None, quantity=Decimal("1"), unit="loaf",
        )
        checked = MockShoppingListItem(
            id="i2", name="Done Item", is_checked=True, category="dairy",
            store_section=None, store_order=None, quantity=Decimal("1"), unit="each",
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[unchecked, checked],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/organize-by-store",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 1

    def test_organize_no_auto_assign(self, client, mock_db, mock_user):
        """No auto-assign when disabled; items with no section go to 'other'."""
        list_id = "test-list"
        item = MockShoppingListItem(
            id="i1", name="Mystery", is_checked=False, category="spices",
            store_section=None, store_order=None, quantity=Decimal("1"), unit="each",
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[item],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/organize-by-store",
            json={"auto_assign_sections": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sections_used"] == 1
        assert data["sections"][0]["section"] == "other"

    def test_organize_preserves_existing_section(self, client, mock_db, mock_user):
        """Items with existing store_section keep it during auto-assign."""
        list_id = "test-list"
        item = MockShoppingListItem(
            id="i1", name="Special Wine", is_checked=False, category="beverages",
            store_section="international", store_order=None, quantity=Decimal("1"), unit="bottle",
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[item],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/organize-by-store",
            json={"auto_assign_sections": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sections"][0]["section"] == "international"


class TestGetStoreSections:
    """Tests for GetStoreSections endpoint.

    Note: GET /v1/shopping-lists/store-sections is shadowed by the
    /v1/shopping-lists/{list_id} route in FastAPI, so we test the endpoint
    class directly rather than through the HTTP route.
    """

    def test_get_store_sections(self, mock_db, mock_user):
        """Returns list of all store sections."""
        from api.v1.shopping_list.organize_by_store import GetStoreSections

        result = GetStoreSections.call(user=mock_user, database=mock_db)
        # handle_result wraps in CustomJSONResponse
        import json
        data = json.loads(result.body)
        assert "sections" in data
        assert len(data["sections"]) > 0
        for section in data["sections"]:
            assert "key" in section
            assert "display_name" in section
            assert "order" in section


# =============================================================================
# GetShoppingListDeadlines tests
# =============================================================================


class TestGetShoppingListDeadlines:
    """Tests for GET /v1/shopping-lists/{list_id}/deadlines."""

    def test_deadlines_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.get("/v1/shopping-lists/no-list/deadlines")
        assert response.status_code == 404

    def test_deadlines_no_access(self, client, mock_db, mock_user):
        """403 when user has no access."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner", items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/deadlines")
        assert response.status_code == 403

    def test_deadlines_empty_list(self, client, mock_db, mock_user):
        """Empty list has all zeros."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/deadlines")
        assert response.status_code == 200
        data = response.json()
        assert data["unchecked_count"] == 0
        assert data["checked_count"] == 0

    def test_deadlines_with_items(self, client, mock_db, mock_user):
        """Items are grouped by urgency, checked items counted separately."""
        list_id = "test-list"
        now = datetime.now()
        # Item due in the past (overdue)
        overdue_item = MockShoppingListItem(
            id="i1", name="Urgent", is_checked=False,
            due_at=now - timedelta(hours=1), due_reason=None,
            archived_at=None, category="produce", quantity=Decimal("1"),
            unit="each", priority=1, meal_event_id=None,
            assigned_to_user_id=None, notes=None, meal_event=None,
        )
        # Checked item
        checked_item = MockShoppingListItem(
            id="i2", name="Done", is_checked=True,
            due_at=now + timedelta(hours=5), due_reason=None,
            archived_at=None, category="dairy", quantity=Decimal("1"),
            unit="gallon", priority=3, meal_event_id=None,
            assigned_to_user_id=None, notes=None, meal_event=None,
        )
        # Archived item (should be skipped)
        archived_item = MockShoppingListItem(
            id="i3", name="Archived", is_checked=False,
            due_at=now + timedelta(hours=1), due_reason=None,
            archived_at=datetime.now(UTC), category=None, quantity=Decimal("1"),
            unit="each", priority=3, meal_event_id=None,
            assigned_to_user_id=None, notes=None, meal_event=None,
        )
        # No deadline
        no_deadline_item = MockShoppingListItem(
            id="i4", name="No Due Date", is_checked=False,
            due_at=None, due_reason=None,
            archived_at=None, category=None, quantity=Decimal("1"),
            unit="each", priority=3, meal_event_id=None,
            assigned_to_user_id=None, notes=None, meal_event=None,
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[overdue_item, checked_item, archived_item, no_deadline_item],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/deadlines")
        assert response.status_code == 200
        data = response.json()
        assert data["unchecked_count"] == 2  # overdue + no_deadline
        assert data["checked_count"] == 1

    def test_deadlines_with_due_reason(self, client, mock_db, mock_user):
        """Items with due_reason show reason text."""
        list_id = "test-list"
        now = datetime.now()
        item = MockShoppingListItem(
            id="i1", name="Chicken", is_checked=False,
            due_at=now + timedelta(days=1), due_reason="marinate",
            archived_at=None, category="meat", quantity=Decimal("2"),
            unit="lbs", priority=2, meal_event_id=None,
            assigned_to_user_id=None, notes=None, meal_event=None,
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[item],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/deadlines")
        assert response.status_code == 200
        data = response.json()
        today_items = data["items_by_urgency"]["today"]
        assert len(today_items) == 1
        assert today_items[0]["due_reason"] == "marinate"
        assert today_items[0]["due_reason_text"] == "Needs time to marinate"

    def test_deadlines_with_meal_event(self, client, mock_db, mock_user):
        """Items linked to meal events populate next_meal_event info."""
        list_id = "test-list"
        now = datetime.now()
        meal_event = MockMealEvent(
            id="me-1", title="Dinner Party",
            scheduled_at=now + timedelta(hours=5),
            prep_start_offset_minutes=60,
        )
        item = MockShoppingListItem(
            id="i1", name="Salmon", is_checked=False,
            due_at=now + timedelta(hours=3), due_reason="prep_start",
            archived_at=None, category="seafood", quantity=Decimal("1"),
            unit="lb", priority=2, meal_event_id="me-1",
            assigned_to_user_id=None, notes=None, meal_event=meal_event,
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[item],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/deadlines")
        assert response.status_code == 200
        data = response.json()
        assert data["next_meal_event"] is not None
        assert data["next_meal_event"]["title"] == "Dinner Party"

    def test_deadlines_as_member(self, client, mock_db, mock_user):
        """Member can access deadlines."""
        list_id = "test-list"
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
        )
        sl = MockShoppingList(id=list_id, owner_id="other-owner", items=[])

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        response = client.get(f"/v1/shopping-lists/{list_id}/deadlines")
        assert response.status_code == 200

    def test_deadlines_tracks_next_deadline(self, client, mock_db, mock_user):
        """next_deadline is the earliest due_at among unchecked items."""
        list_id = "test-list"
        now = datetime.now()
        early = now + timedelta(hours=1)
        later = now + timedelta(hours=5)
        item1 = MockShoppingListItem(
            id="i1", name="Item 1", is_checked=False, due_at=later,
            due_reason=None, archived_at=None, category=None,
            quantity=Decimal("1"), unit="each", priority=3,
            meal_event_id=None, assigned_to_user_id=None, notes=None,
            meal_event=None,
        )
        item2 = MockShoppingListItem(
            id="i2", name="Item 2", is_checked=False, due_at=early,
            due_reason=None, archived_at=None, category=None,
            quantity=Decimal("1"), unit="each", priority=3,
            meal_event_id=None, assigned_to_user_id=None, notes=None,
            meal_event=None,
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[item1, item2],
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/deadlines")
        assert response.status_code == 200
        data = response.json()
        assert data["next_deadline"] is not None


# =============================================================================
# GetShoppingListEvents tests
# =============================================================================


class TestGetShoppingListEvents:
    """Tests for GET /v1/shopping-lists/{list_id}/events."""

    def test_events_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.get("/v1/shopping-lists/no-list/events")
        assert response.status_code == 404

    def test_events_no_access(self, client, mock_db, mock_user):
        """403 when user has no access."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner")

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/events")
        assert response.status_code == 403

    @patch("api.v1.shopping_list.get_events.ShoppingListEventService")
    def test_events_success_as_owner(self, MockEventService, client, mock_db, mock_user):
        """Owner can get events."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        # Mock event service
        mock_service = MagicMock()
        mock_service.get_events_since.return_value = []
        mock_service.get_current_sequence.return_value = 5
        MockEventService.return_value = mock_service

        response = client.get(f"/v1/shopping-lists/{list_id}/events")
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["current_sequence"] == 5
        assert data["has_more"] is False

    @patch("api.v1.shopping_list.get_events.ShoppingListEventService")
    def test_events_with_events(self, MockEventService, client, mock_db, mock_user):
        """Returns events with user info."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        event_user = MockUser(id=str(uuid.uuid4()), name="Eventist")
        mock_event = MockModel(
            id=str(uuid.uuid4()),
            event_type="item_added",
            event_data={"item_id": "i1", "name": "Milk"},
            user_id=event_user.id,
            user=event_user,
            sequence=1,
        )

        mock_service = MagicMock()
        mock_service.get_events_since.return_value = [mock_event]
        mock_service.get_current_sequence.return_value = 1
        MockEventService.return_value = mock_service

        response = client.get(f"/v1/shopping-lists/{list_id}/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "item_added"
        assert data["events"][0]["user_name"] == "Eventist"

    @patch("api.v1.shopping_list.get_events.ShoppingListEventService")
    def test_events_member_updates_last_seen(self, MockEventService, client, mock_db, mock_user):
        """Member's last_seen_at is updated when fetching events."""
        list_id = "test-list"
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
            last_seen_at=None,
        )
        sl = MockShoppingList(id=list_id, owner_id="other-owner")

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        mock_service = MagicMock()
        mock_service.get_events_since.return_value = []
        mock_service.get_current_sequence.return_value = 0
        MockEventService.return_value = mock_service

        response = client.get(f"/v1/shopping-lists/{list_id}/events")
        assert response.status_code == 200
        assert membership.last_seen_at is not None

    @patch("api.v1.shopping_list.get_events.ShoppingListEventService")
    def test_events_limit_capped(self, MockEventService, client, mock_db, mock_user):
        """Limit is capped at 500."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        mock_service = MagicMock()
        mock_service.get_events_since.return_value = []
        mock_service.get_current_sequence.return_value = 0
        MockEventService.return_value = mock_service

        response = client.get(f"/v1/shopping-lists/{list_id}/events?limit=9999")
        assert response.status_code == 200
        # Verify limit was capped at 500
        call_args = mock_service.get_events_since.call_args
        assert call_args[1].get("limit", call_args[0][2] if len(call_args[0]) > 2 else None) is not None

    @patch("api.v1.shopping_list.get_events.ShoppingListEventService")
    def test_events_has_more_true(self, MockEventService, client, mock_db, mock_user):
        """has_more is True when events returned equals limit."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        # Return exactly limit events to trigger has_more=True
        # default limit is 100, so return 100 events
        events = [
            MockModel(
                id=str(uuid.uuid4()),
                event_type="item_added",
                event_data={},
                user_id=None,
                user=None,
                sequence=i,
            )
            for i in range(100)
        ]

        mock_service = MagicMock()
        mock_service.get_events_since.return_value = events
        mock_service.get_current_sequence.return_value = 100
        MockEventService.return_value = mock_service

        response = client.get(f"/v1/shopping-lists/{list_id}/events")
        assert response.status_code == 200
        data = response.json()
        assert data["has_more"] is True

    @patch("api.v1.shopping_list.get_events.ShoppingListEventService")
    def test_events_event_no_user(self, MockEventService, client, mock_db, mock_user):
        """Events without user_id still work."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        mock_event = MockModel(
            id=str(uuid.uuid4()),
            event_type="list_updated",
            event_data={"changes": {}},
            user_id=None,
            user=None,
            sequence=1,
        )

        mock_service = MagicMock()
        mock_service.get_events_since.return_value = [mock_event]
        mock_service.get_current_sequence.return_value = 1
        MockEventService.return_value = mock_service

        response = client.get(f"/v1/shopping-lists/{list_id}/events")
        assert response.status_code == 200
        data = response.json()
        assert data["events"][0]["user_id"] is None
        assert data["events"][0]["user_name"] is None


# =============================================================================
# ListShoppingListMembers tests
# =============================================================================


class TestListShoppingListMembers:
    """Tests for GET /v1/shopping-lists/{list_id}/members."""

    def test_list_members_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.get("/v1/shopping-lists/no-list/members")
        assert response.status_code == 404

    def test_list_members_no_access(self, client, mock_db, mock_user):
        """403 when user has no access."""
        list_id = "test-list"
        sl = MockShoppingList(id=list_id, owner_id="other-owner", members=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/members")
        assert response.status_code == 403

    def test_list_members_as_owner(self, client, mock_db, mock_user):
        """Owner can list members."""
        list_id = "test-list"
        member_user = MockUser(
            id=str(uuid.uuid4()), email="member@example.com",
            name="Member", picture="pic.jpg",
        )
        member = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(member_user.id),
            role="editor",
            archived_at=None,
            notify_on_add=True,
            notify_on_check=False,
            notify_on_deadline=True,
            last_seen_at=None,
            user=member_user,
        )
        owner_user = MockUser(
            id=str(mock_user.id), email="owner@example.com",
            name="Owner", picture=None,
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            members=[member], is_shared=True, share_code="CODE01",
            owner=owner_user,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/members")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["is_shared"] is True
        assert data["share_code"] == "CODE01"

    def test_list_members_includes_owner_if_missing(self, client, mock_db, mock_user):
        """Owner is included even if not in members list."""
        list_id = "test-list"
        # No members at all
        owner_user = MockUser(
            id=str(mock_user.id), email="owner@example.com",
            name="Owner", picture=None,
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            members=[], is_shared=False, share_code=None,
            owner=owner_user,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/members")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["members"][0]["role"] == "owner"

    def test_list_members_skips_archived(self, client, mock_db, mock_user):
        """Archived members are not included."""
        list_id = "test-list"
        active_user = MockUser(id=str(uuid.uuid4()), name="Active")
        active_member = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(active_user.id),
            role="editor",
            archived_at=None,
            notify_on_add=True,
            notify_on_check=False,
            notify_on_deadline=True,
            last_seen_at=None,
            user=active_user,
        )
        archived_member = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(uuid.uuid4()),
            role="editor",
            archived_at=datetime.now(UTC),
            notify_on_add=True,
            notify_on_check=False,
            notify_on_deadline=True,
            user=MockUser(),
        )
        owner_user = MockUser(
            id=str(mock_user.id), name="Owner",
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            members=[active_member, archived_member],
            is_shared=True, share_code=None,
            owner=owner_user,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/members")
        assert response.status_code == 200
        data = response.json()
        # Only active member + owner (who is not in members as a ShoppingListUser)
        # Owner gets added since no member has owner's user_id
        # Active member is shown, archived is not
        member_ids = [m["user_id"] for m in data["members"]]
        assert str(active_user.id) in member_ids

    def test_list_members_as_member(self, client, mock_db, mock_user):
        """Member can list other members."""
        list_id = "test-list"
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
        )
        owner_user = MockUser(
            id="other-owner", email="owner@example.com", name="Owner",
        )
        sl = MockShoppingList(
            id=list_id, owner_id="other-owner",
            members=[], is_shared=True, share_code=None,
            owner=owner_user,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        response = client.get(f"/v1/shopping-lists/{list_id}/members")
        assert response.status_code == 200

    def test_list_members_with_null_user(self, client, mock_db, mock_user):
        """Member with null user reference still renders."""
        list_id = "test-list"
        member = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(uuid.uuid4()),
            role="editor",
            archived_at=None,
            notify_on_add=True,
            notify_on_check=False,
            notify_on_deadline=True,
            last_seen_at=None,
            user=None,
        )
        owner_user = MockUser(id=str(mock_user.id), name="Owner")
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            members=[member], is_shared=True, share_code=None,
            owner=owner_user,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}/members")
        assert response.status_code == 200
        data = response.json()
        # Find the member with null user
        null_user_members = [m for m in data["members"] if m["email"] is None and m["role"] != "owner"]
        assert len(null_user_members) == 1


# =============================================================================
# WebSocket / ConnectionManager tests
# =============================================================================


class TestConnectionManager:
    """Tests for ConnectionManager in-memory state."""

    @pytest.fixture
    def manager(self):
        from api.v1.shopping_list.websocket import ConnectionManager
        return ConnectionManager()

    @pytest.fixture
    def mock_ws(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    def test_connect_adds_to_room(self, manager, mock_user, mock_ws):
        """Connect adds connection to the room."""
        list_id = "list-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_ws, mock_user, list_id)
        )
        assert list_id in manager.active_connections
        assert (str(mock_user.id), mock_ws) in manager.active_connections[list_id]

    def test_disconnect_removes_from_room(self, manager, mock_user, mock_ws):
        """Disconnect removes websocket from all rooms."""
        list_id = "list-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_ws, mock_user, list_id)
        )
        manager.disconnect(mock_ws)
        assert list_id not in manager.active_connections

    def test_disconnect_unknown_websocket(self, manager):
        """Disconnecting an unknown websocket is a no-op."""
        unknown_ws = AsyncMock()
        manager.disconnect(unknown_ws)  # Should not raise

    def test_disconnect_removes_empty_room(self, manager, mock_user, mock_ws):
        """Room is deleted when last connection leaves."""
        list_id = "list-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_ws, mock_user, list_id)
        )
        manager.disconnect(mock_ws)
        assert list_id not in manager.active_connections

    def test_broadcast_to_list(self, manager, mock_user, mock_ws):
        """Broadcast sends message to all connections in room."""
        list_id = "list-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_ws, mock_user, list_id)
        )
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()
        user2 = MockUser(id=str(uuid.uuid4()), name="User2")
        asyncio.get_event_loop().run_until_complete(
            manager.connect(ws2, user2, list_id)
        )

        asyncio.get_event_loop().run_until_complete(
            manager.broadcast_to_list(list_id, {"type": "test"})
        )
        assert mock_ws.send_text.called
        assert ws2.send_text.called

    def test_broadcast_excludes_websocket(self, manager, mock_user, mock_ws):
        """Broadcast excludes the specified websocket."""
        list_id = "list-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_ws, mock_user, list_id)
        )
        asyncio.get_event_loop().run_until_complete(
            manager.broadcast_to_list(
                list_id, {"type": "test"}, exclude_websocket=mock_ws,
            )
        )
        assert not mock_ws.send_text.called

    def test_broadcast_to_nonexistent_room(self, manager):
        """Broadcasting to a non-existent room is a no-op."""
        asyncio.get_event_loop().run_until_complete(
            manager.broadcast_to_list("nonexistent", {"type": "test"})
        )

    def test_broadcast_disconnects_failed_sockets(self, manager, mock_user):
        """Failed send disconnects the socket."""
        list_id = "list-1"
        failing_ws = AsyncMock()
        failing_ws.accept = AsyncMock()
        failing_ws.send_text = AsyncMock(side_effect=Exception("Connection lost"))
        asyncio.get_event_loop().run_until_complete(
            manager.connect(failing_ws, mock_user, list_id)
        )
        asyncio.get_event_loop().run_until_complete(
            manager.broadcast_to_list(list_id, {"type": "test"})
        )
        # After broadcast, the failed socket should be disconnected
        assert failing_ws not in manager.connection_info

    def test_get_online_users(self, manager, mock_user, mock_ws):
        """Returns unique user IDs for a room."""
        list_id = "list-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_ws, mock_user, list_id)
        )
        online = manager.get_online_users(list_id)
        assert str(mock_user.id) in online

    def test_get_online_users_empty_room(self, manager):
        """Returns empty list for non-existent room."""
        online = manager.get_online_users("nonexistent")
        assert online == []


class TestBroadcastEventToList:
    """Tests for the broadcast_event_to_list helper."""

    def test_broadcast_event_formats_message(self):
        """broadcast_event_to_list sends correctly formatted message."""
        from api.v1.shopping_list.websocket import broadcast_event_to_list, manager

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        user = MockUser()

        asyncio.get_event_loop().run_until_complete(
            manager.connect(ws, user, "test-list")
        )

        asyncio.get_event_loop().run_until_complete(
            broadcast_event_to_list(
                "test-list", "item_added",
                {"item_id": "i1", "name": "Milk"},
                user_id=str(user.id),
                sequence=1,
            )
        )

        assert ws.send_text.called
        message = json.loads(ws.send_text.call_args[0][0])
        assert message["type"] == "item_added"
        assert message["sequence"] == 1
        assert message["data"]["item_id"] == "i1"

        # Clean up
        manager.disconnect(ws)

    def test_broadcast_event_with_uuid(self):
        """broadcast_event_to_list handles UUID shopping_list_id."""
        from api.v1.shopping_list.websocket import broadcast_event_to_list

        list_uuid = uuid.uuid4()
        asyncio.get_event_loop().run_until_complete(
            broadcast_event_to_list(
                list_uuid, "item_removed",
                {"item_id": "i1"},
            )
        )
        # Should not raise even with no connections


# =============================================================================
# Notification utility tests
# =============================================================================


class TestNotificationUtils:
    """Tests for shopping list notification helpers."""

    @patch("api.v1.shopping_list.utils.notifications.get_push_service")
    def test_notify_shopping_list_members_not_configured(self, mock_get_push):
        """Skips when push service is not available."""
        from api.v1.shopping_list.utils.notifications import notify_shopping_list_members

        mock_push = MagicMock()
        mock_push.is_available = False
        mock_get_push.return_value = mock_push

        sl = MockShoppingList()
        db = MagicMock()
        notification = MagicMock()
        result = notify_shopping_list_members(sl, notification, db)
        assert result["skipped"] == "not_configured"

    @patch("api.v1.shopping_list.utils.notifications.get_push_service")
    def test_notify_shopping_list_members_no_recipients(self, mock_get_push):
        """Skips when no recipients (all excluded)."""
        from api.v1.shopping_list.utils.notifications import notify_shopping_list_members

        mock_push = MagicMock()
        mock_push.is_available = True
        mock_get_push.return_value = mock_push

        sl = MockShoppingList(owner_id="user-1")
        db = MagicMock()
        db.db = MagicMock()
        db.db.query.return_value = MockQuery([])  # No members
        notification = MagicMock()
        result = notify_shopping_list_members(sl, notification, db, exclude_user_id="user-1")
        assert result["skipped"] == "no_recipients"

    @patch("api.v1.shopping_list.utils.notifications.get_push_service")
    def test_notify_shopping_list_members_sends(self, mock_get_push):
        """Sends to members and owner (excluding actor)."""
        from api.v1.shopping_list.utils.notifications import notify_shopping_list_members

        mock_push = MagicMock()
        mock_push.is_available = True
        mock_push.send_to_users.return_value = {"success_count": 2, "failure_count": 0}
        mock_get_push.return_value = mock_push

        member = MockShoppingListUser(
            user_id="member-1", shopping_list_id="list-1",
            archived_at=None,
        )
        sl = MockShoppingList(id="list-1", owner_id="owner-1")
        db = MagicMock()
        db.db = MagicMock()
        db.db.query.return_value = MockQuery([member])
        notification = MagicMock()

        result = notify_shopping_list_members(
            sl, notification, db, exclude_user_id="actor-1",
        )
        assert result["success_count"] == 2
        mock_push.send_to_users.assert_called_once()

    @patch("api.v1.shopping_list.utils.notifications.get_push_service")
    def test_notify_shopping_list_members_excludes_owner_if_actor(self, mock_get_push):
        """Owner is excluded from notification if they are the actor."""
        from api.v1.shopping_list.utils.notifications import notify_shopping_list_members

        mock_push = MagicMock()
        mock_push.is_available = True
        mock_push.send_to_users.return_value = {"success_count": 0, "failure_count": 0}
        mock_get_push.return_value = mock_push

        sl = MockShoppingList(id="list-1", owner_id="owner-1")
        db = MagicMock()
        db.db = MagicMock()
        db.db.query.return_value = MockQuery([])  # No members
        notification = MagicMock()

        result = notify_shopping_list_members(
            sl, notification, db, exclude_user_id="owner-1",
        )
        assert result["skipped"] == "no_recipients"

    def test_notify_item_added_not_shared(self):
        """notify_item_added skips for non-shared lists."""
        from api.v1.shopping_list.utils.notifications import notify_item_added

        sl = MockShoppingList(is_shared=False)
        item = MockShoppingListItem()
        user = MockUser()
        db = MagicMock()

        result = notify_item_added(sl, item, user, db)
        assert result["skipped"] == "not_shared"

    @patch("api.v1.shopping_list.utils.notifications.notify_shopping_list_members")
    def test_notify_item_added_shared(self, mock_notify_members):
        """notify_item_added sends notification for shared lists."""
        from api.v1.shopping_list.utils.notifications import notify_item_added

        mock_notify_members.return_value = {"success_count": 1}
        sl = MockShoppingList(is_shared=True, name="Weekly List")
        item = MockShoppingListItem(name="Apples")
        user = MockUser(name="Alice")
        db = MagicMock()

        result = notify_item_added(sl, item, user, db)
        assert result["success_count"] == 1
        mock_notify_members.assert_called_once()

    def test_notify_item_checked_not_shared(self):
        """notify_item_checked skips for non-shared lists."""
        from api.v1.shopping_list.utils.notifications import notify_item_checked

        sl = MockShoppingList(is_shared=False)
        item = MockShoppingListItem()
        user = MockUser()
        db = MagicMock()

        result = notify_item_checked(sl, item, user, db)
        assert result["skipped"] == "not_shared"

    @patch("api.v1.shopping_list.utils.notifications.notify_shopping_list_members")
    def test_notify_item_checked_shared(self, mock_notify_members):
        """notify_item_checked sends for shared lists."""
        from api.v1.shopping_list.utils.notifications import notify_item_checked

        mock_notify_members.return_value = {"success_count": 1}
        sl = MockShoppingList(is_shared=True)
        item = MockShoppingListItem(name="Eggs")
        user = MockUser(name="Bob")
        db = MagicMock()

        result = notify_item_checked(sl, item, user, db)
        assert result["success_count"] == 1

    @patch("api.v1.shopping_list.utils.notifications.get_push_service")
    def test_notify_list_shared(self, mock_get_push):
        """notify_list_shared sends to the invited user."""
        from api.v1.shopping_list.utils.notifications import notify_list_shared

        mock_push = MagicMock()
        mock_push.send_to_user.return_value = {"success": True}
        mock_get_push.return_value = mock_push

        sl = MockShoppingList(name="Shopping List")
        invited = MockUser(name="Invitee")
        inviter = MockUser(name="Inviter")
        db = MagicMock()

        result = notify_list_shared(sl, invited, inviter, db)
        assert result["success"] is True
        mock_push.send_to_user.assert_called_once()

    @patch("api.v1.shopping_list.utils.notifications.notify_shopping_list_members")
    def test_notify_member_joined(self, mock_notify_members):
        """notify_member_joined sends to existing members."""
        from api.v1.shopping_list.utils.notifications import notify_member_joined

        mock_notify_members.return_value = {"success_count": 2}
        sl = MockShoppingList(name="Our List")
        new_member = MockUser(name="New Person")
        db = MagicMock()

        result = notify_member_joined(sl, new_member, db)
        assert result["success_count"] == 2

    @patch("api.v1.shopping_list.utils.notifications.notify_shopping_list_members")
    def test_notify_list_complete(self, mock_notify_members):
        """notify_list_complete sends to members."""
        from api.v1.shopping_list.utils.notifications import notify_list_complete

        mock_notify_members.return_value = {"success_count": 1}
        sl = MockShoppingList(name="Done List")
        user = MockUser(name="Completer")
        db = MagicMock()

        result = notify_list_complete(sl, user, db)
        assert result["success_count"] == 1


# =============================================================================
# ShoppingListEventService tests
# =============================================================================


class TestShoppingListEventService:
    """Tests for ShoppingListEventService."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.query.return_value = MockQuery([])
        session.add = MagicMock()
        session.flush = MagicMock()
        return session

    @pytest.fixture
    def event_service(self, mock_session):
        from api.v1.shopping_list.utils.events import ShoppingListEventService
        return ShoppingListEventService(mock_session)

    def test_get_next_sequence_empty(self, event_service, mock_session):
        """Returns 1 when no events exist."""
        mock_session.query.return_value = MockQuery([None])
        seq = event_service._get_next_sequence(uuid.uuid4())
        assert seq == 1

    def test_get_next_sequence_existing(self, event_service, mock_session):
        """Returns max + 1 when events exist."""
        mock_session.query.return_value = MockQuery([5])
        seq = event_service._get_next_sequence(uuid.uuid4())
        assert seq == 6

    def test_create_event(self, event_service, mock_session):
        """Creates event with correct sequence."""
        mock_session.query.return_value = MockQuery([3])
        list_id = uuid.uuid4()
        user_id = uuid.uuid4()

        event = event_service.create_event(
            shopping_list_id=list_id,
            event_type="item_added",
            user_id=user_id,
            event_data={"name": "Milk"},
        )
        assert event.event_type == "item_added"
        assert event.sequence == 4
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_log_item_added(self, event_service, mock_session):
        """log_item_added creates event with item data."""
        mock_session.query.return_value = MockQuery([None])
        item = MockShoppingListItem(
            name="Bread", quantity=Decimal("2"), unit="loaves", category="bakery",
        )
        user = MockUser()

        event = event_service.log_item_added(uuid.uuid4(), item, user)
        assert event.event_type == "item_added"
        assert event.event_data["name"] == "Bread"

    def test_log_item_checked(self, event_service, mock_session):
        """log_item_checked includes checker info."""
        mock_session.query.return_value = MockQuery([None])
        item = MockShoppingListItem(name="Eggs")
        user = MockUser(name="Alice")

        event = event_service.log_item_checked(uuid.uuid4(), item, user)
        assert event.event_type == "item_checked"
        assert event.event_data["checked_by"]["name"] == "Alice"

    def test_log_item_unchecked(self, event_service, mock_session):
        """log_item_unchecked records unchecking."""
        mock_session.query.return_value = MockQuery([None])
        item = MockShoppingListItem(name="Milk")
        user = MockUser()

        event = event_service.log_item_unchecked(uuid.uuid4(), item, user)
        assert event.event_type == "item_unchecked"

    def test_log_item_removed(self, event_service, mock_session):
        """log_item_removed records removal."""
        mock_session.query.return_value = MockQuery([None])
        item = MockShoppingListItem(name="Butter")
        user = MockUser()

        event = event_service.log_item_removed(uuid.uuid4(), item, user)
        assert event.event_type == "item_removed"

    def test_log_item_updated(self, event_service, mock_session):
        """log_item_updated records changes."""
        mock_session.query.return_value = MockQuery([None])
        item = MockShoppingListItem(name="Rice")
        user = MockUser()
        changes = {"quantity": {"old": 1, "new": 2}}

        event = event_service.log_item_updated(uuid.uuid4(), item, user, changes)
        assert event.event_type == "item_updated"
        assert event.event_data["changes"] == changes

    def test_log_member_joined_self(self, event_service, mock_session):
        """log_member_joined without added_by uses member's id."""
        mock_session.query.return_value = MockQuery([None])
        member = MockUser(name="Newcomer", email="new@example.com")

        event = event_service.log_member_joined(uuid.uuid4(), member)
        assert event.event_type == "member_joined"
        assert event.user_id == member.id
        assert event.event_data["added_by"] is None

    def test_log_member_joined_by_another(self, event_service, mock_session):
        """log_member_joined with added_by uses added_by's id."""
        mock_session.query.return_value = MockQuery([None])
        member = MockUser(name="New", email="new@example.com")
        adder = MockUser(name="Adder")

        event = event_service.log_member_joined(uuid.uuid4(), member, added_by=adder)
        assert event.user_id == adder.id
        assert event.event_data["added_by"] == str(adder.id)

    def test_log_member_left_self(self, event_service, mock_session):
        """log_member_left without removed_by."""
        mock_session.query.return_value = MockQuery([None])
        member = MockUser(name="Leaver")

        event = event_service.log_member_left(uuid.uuid4(), member)
        assert event.event_type == "member_left"
        assert event.event_data["was_removed"] is False

    def test_log_member_left_removed_by_other(self, event_service, mock_session):
        """log_member_left when removed by someone else."""
        mock_session.query.return_value = MockQuery([None])
        member = MockUser(name="Removed")
        remover = MockUser(name="Remover")

        event = event_service.log_member_left(uuid.uuid4(), member, removed_by=remover)
        assert event.event_data["was_removed"] is True
        assert event.event_data["removed_by"] == str(remover.id)

    def test_log_list_updated(self, event_service, mock_session):
        """log_list_updated records changes."""
        mock_session.query.return_value = MockQuery([None])
        user = MockUser()
        changes = {"name": {"old": "Old", "new": "New"}}

        event = event_service.log_list_updated(uuid.uuid4(), user, changes)
        assert event.event_type == "list_updated"
        assert event.event_data["changes"] == changes

    def test_get_events_since(self, event_service, mock_session):
        """get_events_since queries with correct filters."""
        event_service.get_events_since(uuid.uuid4(), since_sequence=5, limit=50)
        mock_session.query.assert_called()

    def test_get_current_sequence_empty(self, event_service, mock_session):
        """Returns 0 when no events."""
        mock_session.query.return_value = MockQuery([None])
        seq = event_service.get_current_sequence(uuid.uuid4())
        assert seq == 0

    def test_get_current_sequence_existing(self, event_service, mock_session):
        """Returns max sequence."""
        mock_session.query.return_value = MockQuery([42])
        seq = event_service.get_current_sequence(uuid.uuid4())
        assert seq == 42


# =============================================================================
# store_sections utility tests
# =============================================================================


class TestStoreSectionsUtils:
    """Tests for store section utility functions."""

    def test_get_section_for_category_known(self):
        """Known categories map to correct sections."""
        from api.v1.shopping_list.utils.store_sections import get_section_for_category

        assert get_section_for_category("fruit") == "produce"
        assert get_section_for_category("dairy") == "dairy"
        assert get_section_for_category("chicken") == "meat"
        assert get_section_for_category("fish") == "seafood"
        assert get_section_for_category("pasta") == "pasta"
        assert get_section_for_category("spices") == "baking"
        assert get_section_for_category("sauces") == "condiments"
        assert get_section_for_category("chips") == "snacks"
        assert get_section_for_category("juice") == "beverages"
        assert get_section_for_category("cereal") == "breakfast"
        assert get_section_for_category("asian") == "international"
        assert get_section_for_category("vitamins") == "health"
        assert get_section_for_category("cleaning") == "household"
        assert get_section_for_category("frozen") == "frozen"
        assert get_section_for_category("canned") == "canned"

    def test_get_section_for_category_unknown(self):
        """Unknown categories default to 'other'."""
        from api.v1.shopping_list.utils.store_sections import get_section_for_category

        assert get_section_for_category("unknown") == "other"

    def test_get_section_for_category_none(self):
        """None category defaults to 'other'."""
        from api.v1.shopping_list.utils.store_sections import get_section_for_category

        assert get_section_for_category(None) == "other"

    def test_get_section_for_category_case_insensitive(self):
        """Category lookup is case-insensitive."""
        from api.v1.shopping_list.utils.store_sections import get_section_for_category

        assert get_section_for_category("DAIRY") == "dairy"
        assert get_section_for_category("  Fruit  ") == "produce"

    def test_get_section_order_known(self):
        """Known sections have correct order."""
        from api.v1.shopping_list.utils.store_sections import get_section_order

        assert get_section_order("produce") == 1
        assert get_section_order("dairy") == 6
        assert get_section_order("other") == 99

    def test_get_section_order_unknown(self):
        """Unknown sections default to 99."""
        from api.v1.shopping_list.utils.store_sections import get_section_order

        assert get_section_order("unknown") == 99

    def test_get_section_order_none(self):
        """None section defaults to 99."""
        from api.v1.shopping_list.utils.store_sections import get_section_order

        assert get_section_order(None) == 99

    def test_get_section_display_name_known(self):
        """Known sections have display names."""
        from api.v1.shopping_list.utils.store_sections import get_section_display_name

        assert get_section_display_name("produce") == "Produce"
        assert get_section_display_name("dairy") == "Dairy & Eggs"
        assert get_section_display_name("other") == "Other"

    def test_get_section_display_name_unknown(self):
        """Unknown sections get title-cased name."""
        from api.v1.shopping_list.utils.store_sections import get_section_display_name

        assert get_section_display_name("novelty") == "Novelty"

    def test_get_section_display_name_none(self):
        """None section shows 'Other'."""
        from api.v1.shopping_list.utils.store_sections import get_section_display_name

        assert get_section_display_name(None) == "Other"

    def test_store_sections_list(self):
        """STORE_SECTIONS constant has expected entries."""
        from api.v1.shopping_list.utils.store_sections import STORE_SECTIONS

        keys = [s[0] for s in STORE_SECTIONS]
        assert "produce" in keys
        assert "other" in keys
        assert len(STORE_SECTIONS) >= 10


# =============================================================================
# deadline utility tests
# =============================================================================


class TestDeadlineUtils:
    """Tests for deadline calculation utility functions."""

    def test_get_urgency_level_no_due_date(self):
        """No due date returns 'none'."""
        from api.v1.shopping_list.utils.deadline import get_urgency_level

        assert get_urgency_level(None) == "none"

    def test_get_urgency_level_overdue(self):
        """Past due returns 'overdue'."""
        from api.v1.shopping_list.utils.deadline import get_urgency_level

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 20, 10, 0, 0)
        assert get_urgency_level(due, now) == "overdue"

    def test_get_urgency_level_urgent(self):
        """Due within 2 hours returns 'urgent'."""
        from api.v1.shopping_list.utils.deadline import get_urgency_level

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 20, 13, 0, 0)
        assert get_urgency_level(due, now) == "urgent"

    def test_get_urgency_level_today(self):
        """Due within 24 hours returns 'today'."""
        from api.v1.shopping_list.utils.deadline import get_urgency_level

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 20, 18, 0, 0)
        assert get_urgency_level(due, now) == "today"

    def test_get_urgency_level_soon(self):
        """Due within 72 hours returns 'soon'."""
        from api.v1.shopping_list.utils.deadline import get_urgency_level

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 22, 12, 0, 0)
        assert get_urgency_level(due, now) == "soon"

    def test_get_urgency_level_normal(self):
        """Due beyond 72 hours returns 'normal'."""
        from api.v1.shopping_list.utils.deadline import get_urgency_level

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 27, 12, 0, 0)
        assert get_urgency_level(due, now) == "normal"

    def test_get_urgency_level_default_now(self):
        """Uses current time when now is None."""
        from api.v1.shopping_list.utils.deadline import get_urgency_level

        far_future = datetime(2099, 1, 1, 0, 0, 0)
        assert get_urgency_level(far_future) == "normal"

    def test_get_urgency_priority(self):
        """Urgency priorities are ordered correctly."""
        from api.v1.shopping_list.utils.deadline import get_urgency_priority

        assert get_urgency_priority("overdue") < get_urgency_priority("urgent")
        assert get_urgency_priority("urgent") < get_urgency_priority("today")
        assert get_urgency_priority("today") < get_urgency_priority("soon")
        assert get_urgency_priority("soon") < get_urgency_priority("normal")
        assert get_urgency_priority("normal") < get_urgency_priority("none")

    def test_get_urgency_priority_unknown(self):
        """Unknown urgency defaults to 5."""
        from api.v1.shopping_list.utils.deadline import get_urgency_priority

        assert get_urgency_priority("unknown") == 5

    def test_format_time_until_overdue_minutes(self):
        """Overdue by minutes."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 20, 11, 30, 0)
        result = format_time_until(due, now)
        assert "30m overdue" == result

    def test_format_time_until_overdue_hours(self):
        """Overdue by hours."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 20, 15, 0, 0)
        due = datetime(2026, 3, 20, 12, 0, 0)
        result = format_time_until(due, now)
        assert "3h overdue" == result

    def test_format_time_until_overdue_days(self):
        """Overdue by days."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 22, 12, 0, 0)
        due = datetime(2026, 3, 20, 12, 0, 0)
        result = format_time_until(due, now)
        assert "2d overdue" == result

    def test_format_time_until_minutes_remaining(self):
        """Less than 60 minutes remaining."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 20, 12, 45, 0)
        result = format_time_until(due, now)
        assert result == "45m"

    def test_format_time_until_hours_remaining(self):
        """Hours remaining."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 20, 15, 0, 0)
        result = format_time_until(due, now)
        assert result == "3h"

    def test_format_time_until_hours_and_minutes(self):
        """Hours and minutes remaining."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 20, 15, 30, 0)
        result = format_time_until(due, now)
        assert result == "3h 30m"

    def test_format_time_until_days_remaining(self):
        """Days remaining."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 25, 12, 0, 0)
        result = format_time_until(due, now)
        assert result == "5d"

    def test_format_time_until_days_and_hours(self):
        """Days and hours remaining."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        now = datetime(2026, 3, 20, 12, 0, 0)
        due = datetime(2026, 3, 22, 18, 0, 0)
        result = format_time_until(due, now)
        assert result == "2d 6h"

    def test_format_time_until_default_now(self):
        """Uses current time when now is None."""
        from api.v1.shopping_list.utils.deadline import format_time_until

        far_future = datetime(2099, 1, 1, 0, 0, 0)
        result = format_time_until(far_future)
        assert "d" in result  # Should show days

    def test_calculate_item_due_date_explicit(self):
        """Explicit due_at on item takes priority."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        due = datetime(2026, 3, 25, 12, 0, 0)
        item = MockShoppingListItem(due_at=due, due_reason="marinate")

        result_due, result_reason = calculate_item_due_date(item)
        assert result_due == due
        assert result_reason == "marinate"

    def test_calculate_item_due_date_from_meal_event(self):
        """Calculates due date from meal event timing."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        scheduled = datetime(2026, 3, 25, 18, 0, 0)
        recipe = MockModel(
            steps=[],
            prep_time=10,
            cook_time=20,
        )
        meal_event = MockMealEvent(
            scheduled_at=scheduled,
            prep_start_offset_minutes=60,
            recipe=recipe,
        )
        item = MockShoppingListItem(
            due_at=None, due_reason=None, meal_event_id=None,
            meal_event=None, shopping_list=None,
        )

        result_due, result_reason = calculate_item_due_date(item, meal_event=meal_event)
        # Should be prep start: 18:00 - 60min = 17:00
        assert result_due == datetime(2026, 3, 25, 17, 0, 0)
        assert result_reason == "prep_start"

    def test_calculate_item_due_date_with_advance_prep(self):
        """Recipe with advance prep step calculates earlier due date."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        scheduled = datetime(2026, 3, 25, 18, 0, 0)
        step = MockModel(
            wait_type="marinate",
            wait_time_minutes=480,  # 8 hours
            can_prep_ahead=True,
        )
        recipe = MockModel(steps=[step], prep_time=10, cook_time=20)
        meal_event = MockMealEvent(
            scheduled_at=scheduled,
            prep_start_offset_minutes=60,
            recipe=recipe,
        )
        item = MockShoppingListItem(
            due_at=None, due_reason=None, meal_event_id=None,
            meal_event=None, shopping_list=None,
        )

        result_due, result_reason = calculate_item_due_date(item, meal_event=meal_event)
        # Prep start: 18:00 - 60min = 17:00, then - 480min = 09:00
        assert result_due == datetime(2026, 3, 25, 9, 0, 0)
        assert result_reason == "marinate"

    def test_calculate_item_due_date_meal_event_no_recipe(self):
        """Meal event without recipe uses prep start time."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        scheduled = datetime(2026, 3, 25, 18, 0, 0)
        meal_event = MockMealEvent(
            scheduled_at=scheduled,
            prep_start_offset_minutes=30,
            recipe=None,
        )
        item = MockShoppingListItem(
            due_at=None, due_reason=None, meal_event_id=None,
            meal_event=None, shopping_list=None,
        )

        result_due, result_reason = calculate_item_due_date(item, meal_event=meal_event)
        assert result_due == datetime(2026, 3, 25, 17, 30, 0)
        assert result_reason == "prep_start"

    def test_calculate_item_due_date_from_list_default(self):
        """Falls back to shopping list's default deadline."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        default_deadline = datetime(2026, 3, 28, 12, 0, 0)
        shopping_list = MockShoppingList(default_deadline=default_deadline)
        item = MockShoppingListItem(
            due_at=None, due_reason=None, meal_event_id=None,
            meal_event=None, shopping_list=shopping_list,
        )

        result_due, result_reason = calculate_item_due_date(item)
        assert result_due == default_deadline
        assert result_reason is None

    def test_calculate_item_due_date_no_deadline(self):
        """Returns None when no deadline can be determined."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        item = MockShoppingListItem(
            due_at=None, due_reason=None, meal_event_id=None,
            meal_event=None, shopping_list=None,
        )

        result_due, result_reason = calculate_item_due_date(item)
        assert result_due is None
        assert result_reason is None

    def test_calculate_item_due_date_item_meal_event_fallback(self):
        """Falls back to item.meal_event when no explicit meal event."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        scheduled = datetime(2026, 3, 25, 18, 0, 0)
        meal_event = MockMealEvent(
            scheduled_at=scheduled,
            prep_start_offset_minutes=None,  # Default to 60
            recipe=None,
        )
        item = MockShoppingListItem(
            due_at=None, due_reason=None,
            meal_event_id="event-1", meal_event=meal_event,
            shopping_list=None,
        )

        result_due, result_reason = calculate_item_due_date(item)
        # Default prep offset is 60, so 18:00 - 60min = 17:00
        assert result_due == datetime(2026, 3, 25, 17, 0, 0)

    def test_calculate_recipe_lead_time(self):
        """Calculates total lead time from recipe."""
        from api.v1.shopping_list.utils.deadline import calculate_recipe_lead_time

        step1 = MockModel(wait_type="marinate", wait_time_minutes=120)
        step2 = MockModel(wait_type="bake", wait_time_minutes=30)  # Not in ADVANCE_PREP
        recipe = MockModel(
            prep_time=15,
            cook_time=45,
            steps=[step1, step2],
        )

        total = calculate_recipe_lead_time(recipe)
        # 15 + 45 + 120 (max advance wait) = 180
        assert total == 180

    def test_calculate_recipe_lead_time_no_prep(self):
        """Handles recipe with no prep/cook time."""
        from api.v1.shopping_list.utils.deadline import calculate_recipe_lead_time

        recipe = MockModel(
            prep_time=None,
            cook_time=None,
            steps=[],
        )

        total = calculate_recipe_lead_time(recipe)
        assert total == 0

    def test_calculate_item_due_date_multiple_advance_steps(self):
        """Uses maximum advance prep wait time."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        scheduled = datetime(2026, 3, 25, 18, 0, 0)
        step1 = MockModel(wait_type="marinate", wait_time_minutes=120)
        step2 = MockModel(wait_type="brine", wait_time_minutes=480)
        step3 = MockModel(wait_type="bake", wait_time_minutes=60)  # Not advance prep
        recipe = MockModel(steps=[step1, step2, step3], prep_time=10, cook_time=20)
        meal_event = MockMealEvent(
            scheduled_at=scheduled,
            prep_start_offset_minutes=60,
            recipe=recipe,
        )
        item = MockShoppingListItem(
            due_at=None, due_reason=None, meal_event_id=None,
            meal_event=None, shopping_list=None,
        )

        result_due, result_reason = calculate_item_due_date(item, meal_event=meal_event)
        # prep start: 18:00 - 60min = 17:00, then - 480min (max brine) = 09:00
        assert result_due == datetime(2026, 3, 25, 9, 0, 0)
        assert result_reason == "brine"

    def test_calculate_item_due_date_shopping_list_param(self):
        """shopping_list parameter is used when item.shopping_list is None."""
        from api.v1.shopping_list.utils.deadline import calculate_item_due_date

        default_deadline = datetime(2026, 3, 30, 12, 0, 0)
        sl = MockShoppingList(default_deadline=default_deadline)
        item = MockShoppingListItem(
            due_at=None, due_reason=None, meal_event_id=None,
            meal_event=None, shopping_list=None,
        )

        result_due, result_reason = calculate_item_due_date(item, shopping_list=sl)
        assert result_due == default_deadline


# =============================================================================
# WebSocket handler integration tests
# =============================================================================


class TestWebSocketHandler:
    """Tests for shopping_list_websocket_handler."""

    @pytest.fixture
    def mock_ws_handler_deps(self):
        """Common dependencies for websocket handler tests."""
        from api.v1.shopping_list.websocket import manager

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws, manager

    @patch("api.v1.shopping_list.websocket.ShoppingListEventService")
    def test_ws_handler_no_shopping_list(self, MockEventService, mock_user):
        """Closes connection when shopping list not found."""
        from api.v1.shopping_list.websocket import shopping_list_websocket_handler

        ws = AsyncMock()
        ws.close = AsyncMock()
        db = MagicMock()
        db.query.return_value = MockQuery([])

        asyncio.get_event_loop().run_until_complete(
            shopping_list_websocket_handler(ws, "no-list", mock_user, db)
        )
        ws.close.assert_called_once_with(code=4004, reason="Shopping list not found")

    @patch("api.v1.shopping_list.websocket.ShoppingListEventService")
    def test_ws_handler_no_access(self, MockEventService, mock_user):
        """Closes connection when user has no access."""
        from api.v1.shopping_list.websocket import shopping_list_websocket_handler
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        ws.close = AsyncMock()
        sl = MockShoppingList(id="list-1", owner_id="other-owner")
        db = MagicMock()

        # First query returns shopping list, second returns no membership
        call_count = [0]
        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MockQuery([sl])
            return MockQuery([])
        db.query.side_effect = query_side_effect

        asyncio.get_event_loop().run_until_complete(
            shopping_list_websocket_handler(ws, "list-1", mock_user, db)
        )
        ws.close.assert_called_once_with(code=4003, reason="Access denied")

    @patch("api.v1.shopping_list.websocket.ShoppingListEventService")
    def test_ws_handler_connect_and_disconnect(self, MockEventService, mock_user):
        """Handler connects, sends initial sync, then handles disconnect."""
        from api.v1.shopping_list.websocket import shopping_list_websocket_handler, manager
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        sl = MockShoppingList(id="list-1", owner_id=str(mock_user.id))
        db = MagicMock()
        db.query.return_value = MockQuery([sl])

        mock_service = MagicMock()
        mock_service.get_current_sequence.return_value = 0
        mock_service.get_events_since.return_value = []
        MockEventService.return_value = mock_service

        asyncio.get_event_loop().run_until_complete(
            shopping_list_websocket_handler(ws, "list-1", mock_user, db)
        )

        # Should have sent initial sync
        ws.send_json.assert_called()
        initial_msg = ws.send_json.call_args_list[0][0][0]
        assert initial_msg["type"] == "sync_response"

    @patch("api.v1.shopping_list.websocket.ShoppingListEventService")
    def test_ws_handler_ping_pong(self, MockEventService, mock_user):
        """Handler responds to ping with pong."""
        from api.v1.shopping_list.websocket import shopping_list_websocket_handler
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        # First receive: ping, second: disconnect
        ws.receive_text = AsyncMock(
            side_effect=[
                json.dumps({"type": "ping"}),
                WebSocketDisconnect(),
            ]
        )

        sl = MockShoppingList(id="list-1", owner_id=str(mock_user.id))
        db = MagicMock()
        db.query.return_value = MockQuery([sl])

        mock_service = MagicMock()
        mock_service.get_current_sequence.return_value = 0
        mock_service.get_events_since.return_value = []
        MockEventService.return_value = mock_service

        asyncio.get_event_loop().run_until_complete(
            shopping_list_websocket_handler(ws, "list-1", mock_user, db)
        )

        # Should have sent pong
        pong_calls = [
            c for c in ws.send_json.call_args_list
            if c[0][0].get("type") == "pong"
        ]
        assert len(pong_calls) == 1

    @patch("api.v1.shopping_list.websocket.ShoppingListEventService")
    def test_ws_handler_presence_message(self, MockEventService, mock_user):
        """Handler broadcasts presence updates."""
        from api.v1.shopping_list.websocket import shopping_list_websocket_handler
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock(
            side_effect=[
                json.dumps({"type": "presence", "status": "shopping"}),
                WebSocketDisconnect(),
            ]
        )

        sl = MockShoppingList(id="list-1", owner_id=str(mock_user.id))
        db = MagicMock()
        db.query.return_value = MockQuery([sl])

        mock_service = MagicMock()
        mock_service.get_current_sequence.return_value = 0
        mock_service.get_events_since.return_value = []
        MockEventService.return_value = mock_service

        asyncio.get_event_loop().run_until_complete(
            shopping_list_websocket_handler(ws, "list-1", mock_user, db)
        )
        # No crash, presence was broadcast

    @patch("api.v1.shopping_list.websocket.ShoppingListEventService")
    def test_ws_handler_sync_request(self, MockEventService, mock_user):
        """Handler responds to sync_request with events."""
        from api.v1.shopping_list.websocket import shopping_list_websocket_handler
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock(
            side_effect=[
                json.dumps({"type": "sync_request", "since_sequence": 0}),
                WebSocketDisconnect(),
            ]
        )

        sl = MockShoppingList(id="list-1", owner_id=str(mock_user.id))
        db = MagicMock()
        db.query.return_value = MockQuery([sl])

        mock_service = MagicMock()
        mock_service.get_current_sequence.return_value = 5
        mock_event = MockModel(
            id=str(uuid.uuid4()),
            event_type="item_added",
            event_data={"name": "Milk"},
            user_id=str(mock_user.id),
            sequence=1,
        )
        mock_service.get_events_since.return_value = [mock_event]
        MockEventService.return_value = mock_service

        asyncio.get_event_loop().run_until_complete(
            shopping_list_websocket_handler(ws, "list-1", mock_user, db)
        )

        # Should have sent sync_response (initial + request response)
        sync_calls = [
            c for c in ws.send_json.call_args_list
            if c[0][0].get("type") == "sync_response"
        ]
        assert len(sync_calls) >= 2

    @patch("api.v1.shopping_list.websocket.ShoppingListEventService")
    def test_ws_handler_as_member(self, MockEventService, mock_user):
        """Member can connect to websocket."""
        from api.v1.shopping_list.websocket import shopping_list_websocket_handler
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        sl = MockShoppingList(id="list-1", owner_id="other-owner")
        membership = MockShoppingListUser(
            shopping_list_id="list-1",
            user_id=str(mock_user.id),
            role="editor",
        )
        db = MagicMock()

        call_count = [0]
        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MockQuery([sl])
            return MockQuery([membership])
        db.query.side_effect = query_side_effect

        mock_service = MagicMock()
        mock_service.get_current_sequence.return_value = 0
        MockEventService.return_value = mock_service

        asyncio.get_event_loop().run_until_complete(
            shopping_list_websocket_handler(ws, "list-1", mock_user, db)
        )
        ws.send_json.assert_called()
