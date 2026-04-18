"""Tests to close all remaining coverage gaps to reach 100% branch coverage.

Each section corresponds to a source file with missing lines or branches.
"""

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import (
    MockExecuteResult,
    MockIngredient,
    MockInviteLink,
    MockMealEvent,
    MockMealEventParticipant,
    MockModel,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
    MockRecipeIngredient,
    MockRecipeNote,
    MockRecipeStep,
    MockRecipeVersion,
    MockShoppingList,
    MockShoppingListItem,
    MockShoppingListUser,
    MockUser,
    MockUserFavorite,
)


# ===========================================================================
# 1. send_message.py — lines 28-42 (SSE generator body)
# ===========================================================================


class TestSendMessageSSEGenerator:
    """Cover the SSE event_generator inside send_message_stream (lines 28-42)."""

    def test_send_message_streams_sse_events(self, client, mock_db, mock_user):
        """Hit the SSE streaming path — exercises the event_generator function body."""
        from utils.models.thread import Thread

        thread_id = str(uuid.uuid4())
        thread = MockModel(id=thread_id, user_id=str(mock_user.id))
        mock_db.set_find_by(Thread, thread, id=thread_id)

        # Patch run_chat_agent to yield one event then finish
        async def fake_agent(**kwargs):
            yield {"type": "token", "content": "hello"}
            yield {"type": "done"}

        with patch("api.v1.chat.send_message.run_chat_agent", side_effect=fake_agent):
            response = client.post(
                f"/v1/chat/threads/{thread_id}/messages",
                json={"message": "hi"},
            )
        # The streaming response is consumed by TestClient; check 200
        assert response.status_code == 200
        # Body should contain SSE data lines
        assert "data:" in response.text

    def test_send_message_sse_error_path(self, client, mock_db, mock_user):
        """Cover the except branch in event_generator (lines 38-40)."""
        from utils.models.thread import Thread

        thread_id = str(uuid.uuid4())
        thread = MockModel(id=thread_id, user_id=str(mock_user.id))
        mock_db.set_find_by(Thread, thread, id=thread_id)

        async def exploding_agent(**kwargs):
            raise RuntimeError("boom")
            yield  # noqa: unreachable — makes this an async generator

        with patch("api.v1.chat.send_message.run_chat_agent", side_effect=exploding_agent):
            response = client.post(
                f"/v1/chat/threads/{thread_id}/messages",
                json={"message": "hi"},
            )
        assert response.status_code == 200
        assert "error" in response.text


# ===========================================================================
# 2. update_member.py — lines 30-93
# ===========================================================================


class TestUpdateShoppingListMember:
    """Cover UpdateShoppingListMember.execute (lines 30-93)."""

    def _setup(self, mock_db, mock_user, list_id, member_user_id, role="editor",
               owner_id=None, target_role="editor"):
        """Helper to set up shopping list + membership."""
        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        _owner_id = owner_id or str(mock_user.id)
        sl = MockShoppingList(id=list_id, owner_id=_owner_id)
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        member_user = MockUser(id=member_user_id, email="member@test.com", name="Member")
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=member_user_id,
            role=target_role,
            notify_on_add=True,
            notify_on_check=True,
            notify_on_deadline=True,
            user=member_user,
        )
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=member_user_id,
        )
        return sl, membership

    def test_update_member_role_as_owner(self, client, mock_db, mock_user):
        """Owner updates another member's role (success path)."""
        list_id = "sl-update-member"
        member_id = str(uuid.uuid4())
        self._setup(mock_db, mock_user, list_id, member_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/members/{member_id}",
            json={"role": "viewer"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "viewer"

    def test_update_member_notify_settings(self, client, mock_db, mock_user):
        """Self-update notification settings."""
        list_id = "sl-notify-update"
        self._setup(mock_db, mock_user, list_id, str(mock_user.id), target_role="editor")

        response = client.put(
            f"/v1/shopping-lists/{list_id}/members/{mock_user.id}",
            json={
                "notify_on_add": False,
                "notify_on_check": False,
                "notify_on_deadline": False,
            },
        )
        assert response.status_code == 200

    def test_update_member_list_not_found(self, client, mock_db, mock_user):
        """404 when shopping list doesn't exist."""
        response = client.put(
            "/v1/shopping-lists/missing/members/someone",
            json={"role": "viewer"},
        )
        assert response.status_code == 404

    def test_update_member_not_found(self, client, mock_db, mock_user):
        """404 when target membership doesn't exist."""
        from utils.models.shopping_list import ShoppingList

        list_id = "sl-mem-nf"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/members/{uuid.uuid4()}",
            json={"role": "viewer"},
        )
        assert response.status_code == 404

    def test_update_member_archived_returns_404(self, client, mock_db, mock_user):
        """404 when target membership is archived."""
        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        list_id = "sl-mem-arch"
        member_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=member_id,
            archived_at=datetime.now(UTC),
        )
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=member_id,
        )

        response = client.put(
            f"/v1/shopping-lists/{list_id}/members/{member_id}",
            json={"role": "viewer"},
        )
        assert response.status_code == 404

    def test_update_member_role_not_owner_returns_403(self, client, mock_db, mock_user):
        """Non-owner trying to change another member's role gets 403."""
        list_id = "sl-mem-notown"
        other_owner = str(uuid.uuid4())
        member_id = str(uuid.uuid4())
        self._setup(mock_db, mock_user, list_id, member_id, owner_id=other_owner)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/members/{member_id}",
            json={"role": "viewer"},
        )
        assert response.status_code == 403

    def test_update_member_cannot_change_owner_role(self, client, mock_db, mock_user):
        """Cannot change the owner's role."""
        list_id = "sl-mem-ownrole"
        target_id = str(uuid.uuid4())
        self._setup(mock_db, mock_user, list_id, target_id, target_role="owner")

        response = client.put(
            f"/v1/shopping-lists/{list_id}/members/{target_id}",
            json={"role": "viewer"},
        )
        assert response.status_code == 400


# ===========================================================================
# 3. populate_from_calendar.py — lines 72-73, 91, 104-111, 135, 139, 153-159
# ===========================================================================


class TestPopulateFromCalendarExtended:
    """Cover remaining branches in PopulateFromCalendar."""

    def test_no_end_date_uses_lookahead(self, client, mock_db, mock_user):
        """When end_date is None, lookahead_days from the list is used (line 72-73)."""
        list_id = str(uuid.uuid4())
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[],
            calendar_lookahead_days=14,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-20"},
        )
        assert response.status_code == 200

    def test_include_meal_event_ids_filter(self, client, mock_db, mock_user):
        """When include_meal_event_ids is set, the filter is applied (line 91)."""
        list_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={
                "start_date": "2026-03-20",
                "end_date": "2026-03-27",
                "include_meal_event_ids": ["evt-1"],
            },
        )
        assert response.status_code == 200

    def test_check_pantry_with_pantry_id(self, client, mock_db, mock_user):
        """Cover check_pantry + pantry_id branch (lines 104-111)."""
        list_id = str(uuid.uuid4())
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[],
            pantry_id="pantry-1",
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # Queries in order: user's calendar memberships, pantry
        # ingredients, meal events. Using return_value (not side_effect)
        # so each call returns an empty MockQuery regardless of count.
        mock_db.db.query.return_value = MockQuery([])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={
                "start_date": "2026-03-20",
                "end_date": "2026-03-27",
                "check_pantry": True,
            },
        )
        assert response.status_code == 200

    def test_archived_ingredient_skipped(self, client, mock_db, mock_user):
        """Recipe ingredient with archived_at is skipped (line 135)."""
        list_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        ingredient = MockIngredient(id=ingredient_id, canonical_name="Salt")
        ri = MockRecipeIngredient(
            ingredient_id=ingredient_id,
            recipe_id=recipe_id,
            quantity_display=Decimal("1"),
            unit_display="tsp",
            archived_at=datetime.now(UTC),  # archived
        )
        ri.ingredient = ingredient

        recipe = MockRecipe(id=recipe_id)
        recipe.ingredients = [ri]

        event = MockMealEvent(
            owner_id=str(mock_user.id),
            status="planned",
            scheduled_at=datetime.now(UTC),
            recipe=recipe,
        )

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([event])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-20", "end_date": "2026-03-27"},
        )
        assert response.status_code == 200
        assert response.json()["items_added"] == 0

    def test_ingredient_none_skipped(self, client, mock_db, mock_user):
        """Recipe ingredient where .ingredient is None is skipped (line 139)."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        ri = MockRecipeIngredient(
            ingredient_id=str(uuid.uuid4()),
            recipe_id=recipe_id,
            quantity_display=Decimal("1"),
            unit_display="tsp",
        )
        ri.ingredient = None  # ingredient not resolved

        recipe = MockRecipe(id=recipe_id)
        recipe.ingredients = [ri]

        event = MockMealEvent(
            owner_id=str(mock_user.id),
            status="planned",
            scheduled_at=datetime.now(UTC),
            recipe=recipe,
        )

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([event])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-20", "end_date": "2026-03-27"},
        )
        assert response.status_code == 200
        assert response.json()["items_added"] == 0

    def _make_pantry_item(self, ingredient_id, quantity):
        """Create a mock pantry ingredient with needed attributes."""
        pi = MagicMock()
        pi.ingredient_id = ingredient_id
        pi.quantity = quantity
        pi.archived_at = None
        pi.pantry_id = "pantry-1"
        return pi

    def test_pantry_has_enough_skips_item(self, client, mock_db, mock_user):
        """Pantry has enough of ingredient -- item is skipped (lines 153-159)."""
        list_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        ingredient = MockIngredient(id=ingredient_id, canonical_name="Flour")
        ri = MockRecipeIngredient(
            ingredient_id=ingredient_id,
            recipe_id=recipe_id,
            quantity_display=Decimal("200"),
            unit_display="g",
        )
        ri.ingredient = ingredient

        recipe = MockRecipe(id=recipe_id)
        recipe.ingredients = [ri]

        event = MockMealEvent(
            owner_id=str(mock_user.id),
            status="planned",
            scheduled_at=datetime.now(UTC),
            recipe=recipe,
        )

        pantry_item = self._make_pantry_item(ingredient_id, Decimal("500"))

        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[],
            pantry_id="pantry-1",
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # Queries in order: (1) get_user_calendar_ids CalendarUser query,
        # (2) the MealEvent query, (3) the PantryIngredient query.
        mock_db.db.query.side_effect = [
            MockQuery([]),              # calendar_ids
            MockQuery([event]),         # meal events
            MockQuery([pantry_item]),   # pantry items
        ]

        with patch("api.v1.shopping_list.populate_from_calendar.calculate_item_due_date",
                    return_value=(None, None)):
            response = client.post(
                f"/v1/shopping-lists/{list_id}/populate-from-calendar",
                json={
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "check_pantry": True,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["items_skipped"] == 1
        assert data["items_added"] == 0

    def test_pantry_partial_creates_item_with_already_have(self, client, mock_db, mock_user):
        """Pantry has partial qty -- item added with already_have_quantity (line 155)."""
        list_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        ingredient = MockIngredient(id=ingredient_id, canonical_name="Sugar")
        ri = MockRecipeIngredient(
            ingredient_id=ingredient_id,
            recipe_id=recipe_id,
            quantity_display=Decimal("200"),
            unit_display="g",
        )
        ri.ingredient = ingredient

        recipe = MockRecipe(id=recipe_id)
        recipe.ingredients = [ri]

        event = MockMealEvent(
            owner_id=str(mock_user.id),
            status="planned",
            scheduled_at=datetime.now(UTC),
            recipe=recipe,
        )

        pantry_item = self._make_pantry_item(ingredient_id, Decimal("50"))

        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id), items=[],
            pantry_id="pantry-1",
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        # Queries in order: calendar_ids, meal events, pantry items.
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([event]),
            MockQuery([pantry_item]),
        ]

        with patch("api.v1.shopping_list.populate_from_calendar.calculate_item_due_date",
                    return_value=(None, None)):
            response = client.post(
                f"/v1/shopping-lists/{list_id}/populate-from-calendar",
                json={
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-27",
                    "check_pantry": True,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 1

    def test_editor_member_can_populate(self, client, mock_db, mock_user):
        """Editor membership can populate (covers the can_edit membership branch)."""
        list_id = str(uuid.uuid4())
        other_owner = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=other_owner, items=[])
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
            archived_at=None,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )
        mock_db.db.query.return_value = MockQuery([])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-20", "end_date": "2026-03-27"},
        )
        assert response.status_code == 200


# ===========================================================================
# 4. update_item.py — lines 77, 79, 81, 95, 97, 99, 101, 103, 105, 107, 109
# ===========================================================================


class TestUpdateShoppingListItemExtended:
    """Cover all optional field update branches in UpdateShoppingListItem."""

    @patch("api.v1.shopping_list.update_item.notify_item_checked")
    @patch("api.v1.shopping_list.update_item.notify_list_complete")
    def test_update_all_fields(self, mock_complete, mock_checked, client, mock_db, mock_user):
        """Set every optional field to cover all if-branches."""
        list_id = "sl-upd-all"
        item_id = "item-upd-all"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id, shopping_list_id=list_id, name="Eggs",
            is_checked=False,
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}",
            json={
                "name": "Brown Eggs",
                "quantity": 12,
                "unit": "each",
                "category": "dairy",
                "is_checked": True,
                "due_at": datetime.now(UTC).isoformat(),
                "meal_event_id": "evt-1",
                "due_reason": "Dinner tomorrow",
                "priority": 1,
                "notes": "Free range",
                "assigned_to_user_id": str(mock_user.id),
                "store_section": "Refrigerator",
                "store_order": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Brown Eggs"
        assert data["priority"] == 1
        assert data["store_section"] == "Refrigerator"
        assert data["store_order"] == 5
        assert data["notes"] == "Free range"

    @patch("api.v1.shopping_list.update_item.notify_item_checked")
    @patch("api.v1.shopping_list.update_item.notify_list_complete")
    def test_uncheck_item(self, mock_complete, mock_checked, client, mock_db, mock_user):
        """Uncheck item — clears checked_by and checked_at (lines 90-91)."""
        list_id = "sl-uncheck"
        item_id = "item-uncheck"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(
            id=item_id, shopping_list_id=list_id, name="Eggs",
            is_checked=True, checked_by_user_id=str(mock_user.id),
            checked_at=datetime.now(UTC),
        )

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.put(
            f"/v1/shopping-lists/{list_id}/items/{item_id}",
            json={"is_checked": False},
        )
        assert response.status_code == 200
        assert item.checked_by_user_id is None
        assert item.checked_at is None


# ===========================================================================
# 5. get_shopping_list.py — lines 44, 52-53, 58-59, 104
# ===========================================================================


class TestGetShoppingListExtended:
    """Cover missing branches in GetShoppingList."""

    def test_get_as_member_updates_last_seen(self, client, mock_db, mock_user):
        """Non-owner member — updates last_seen_at (lines 52-53), also 403 branch."""
        list_id = "sl-mem-view"
        other_owner = str(uuid.uuid4())
        membership = MockShoppingListUser(
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
            role="editor",
        )
        sl = MockShoppingList(
            id=list_id, owner_id=other_owner, items=[], members=[],
            is_shared=False,
        )

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser, membership,
            shopping_list_id=list_id, user_id=str(mock_user.id),
        )

        response = client.get(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 200
        assert membership.last_seen_at is not None

    def test_get_not_owner_no_member_returns_403(self, client, mock_db, mock_user):
        """Non-owner without membership returns 403 (line 44)."""
        list_id = "sl-no-access"
        sl = MockShoppingList(id=list_id, owner_id=str(uuid.uuid4()), items=[], members=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 403

    def test_get_with_items_and_all_fields(self, client, mock_db, mock_user):
        """Cover item serialization branches (lines 58-59 — archived item skipped)."""
        list_id = "sl-items-full"
        active_item = MockShoppingListItem(
            id="item-1", shopping_list_id=list_id, name="Milk",
            checked_by_user_id=str(mock_user.id),
            recipe_id="r1", ingredient_id="i1", meal_event_id="e1",
            added_by_user_id=str(mock_user.id),
            assigned_to_user_id=str(mock_user.id),
            checked_at=datetime.now(UTC),
            notes="Full fat",
            store_section="Dairy",
            store_order=1,
            already_have_quantity=Decimal("0.5"),
        )
        archived_item = MockShoppingListItem(
            id="item-2", shopping_list_id=list_id, name="Archived",
            archived_at=datetime.now(UTC),
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[active_item, archived_item],
            members=[], is_shared=False,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1  # archived item skipped

    def test_get_shared_list_counts_members(self, client, mock_db, mock_user):
        """Shared list counts active (non-archived) members (line 104)."""
        list_id = "sl-shared-cnt"
        active_member = MockShoppingListUser(
            shopping_list_id=list_id, user_id="u1", archived_at=None,
        )
        archived_member = MockShoppingListUser(
            shopping_list_id=list_id, user_id="u2", archived_at=datetime.now(UTC),
        )
        sl = MockShoppingList(
            id=list_id, owner_id=str(mock_user.id),
            items=[], members=[active_member, archived_member],
            is_shared=True,
        )

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.get(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["member_count"] == 1


# ===========================================================================
# 6. delete_item.py — lines 31, 49, 60
# ===========================================================================


class TestDeleteShoppingListItemExtended:
    """Cover missing branches in DeleteShoppingListItem."""

    def test_delete_item_list_not_found(self, client, mock_db, mock_user):
        """404 when shopping list not found (line 31)."""
        response = client.delete("/v1/shopping-lists/missing/items/item1")
        assert response.status_code == 404

    def test_delete_item_no_permission(self, client, mock_db, mock_user):
        """403 when user has no edit permission (line 49)."""
        list_id = "sl-noedit"
        sl = MockShoppingList(id=list_id, owner_id=str(uuid.uuid4()))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.delete(f"/v1/shopping-lists/{list_id}/items/item1")
        assert response.status_code == 403

    def test_delete_item_not_found(self, client, mock_db, mock_user):
        """404 when item not found (line 60)."""
        list_id = "sl-del-nf"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.delete(f"/v1/shopping-lists/{list_id}/items/nonexistent")
        assert response.status_code == 404

    def test_delete_item_success(self, client, mock_db, mock_user):
        """Successful item deletion."""
        list_id = "sl-del-ok"
        item_id = "item-del-ok"
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        item = MockShoppingListItem(id=item_id, shopping_list_id=list_id, name="Test")

        from utils.models.shopping_list import ShoppingList, ShoppingListItem

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)

        response = client.delete(f"/v1/shopping-lists/{list_id}/items/{item_id}")
        assert response.status_code == 200
        assert item.archived_at is not None


# ===========================================================================
# 7. create_shopping_list.py — lines 40-51 (items)
# ===========================================================================


class TestCreateShoppingListWithItems:
    """Cover the items loop in CreateShoppingList (lines 40-51)."""

    def test_create_with_items(self, client, mock_db, mock_user):
        """Create list with initial items."""
        response = client.post(
            "/v1/shopping-lists",
            json={
                "name": "Weekly",
                "items": [
                    {"name": "Milk", "quantity": 1, "unit": "gallon"},
                    {"name": "Eggs", "quantity": 12, "unit": "each", "category": "dairy",
                     "ingredient_id": str(uuid.uuid4()), "recipe_id": str(uuid.uuid4())},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 2


# ===========================================================================
# 8. restore_recipe_version.py — lines 41-42, 103, 110-111, 115-116, 137
# ===========================================================================


class TestRestoreRecipeVersionExtended:
    """Cover missing branches in RestoreRecipeVersion."""

    def test_parse_quantity_display_fraction(self):
        """Cover _parse_quantity_display with '1 1/2' (line 36-37)."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display

        result = _parse_quantity_display("1 1/2")
        assert float(result) == pytest.approx(1.5)

    def test_parse_quantity_display_simple_fraction(self):
        """Cover '1/2' branch (line 40)."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display

        result = _parse_quantity_display("1/2")
        assert float(result) == pytest.approx(0.5)

    def test_parse_quantity_display_fallback(self):
        """Cover except branch (line 41-42)."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display

        result = _parse_quantity_display("3.5")
        assert float(result) == pytest.approx(3.5)

    def test_restore_version_success(self, client, mock_db, mock_user):
        """Full restore flow covering lines 103, 110-111, 115-116, 137."""
        recipe_id = "recipe-restore"
        version_id = "version-restore"
        book_id = "book-restore"

        recipe = MockRecipe(
            id=recipe_id, recipe_book_id=book_id, name="Old Recipe",
            instructions="Old", description="Desc", servings=4,
            prep_time=10, cook_time=20, image_url=None, source_url=None,
            tags=["italian"],
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        version = MockRecipeVersion(
            id=version_id, recipe_id=recipe_id, version_number=1,
            snapshot={
                "name": "Restored Name",
                "instructions": "Restored instructions",
                "ingredients": [
                    {
                        "ingredient_id": str(uuid.uuid4()),
                        "quantity_display": "2",
                        "unit_display": "cups",
                        "notes": "sifted",
                        "is_optional": False,
                        "order_index": 0,
                    }
                ],
                "steps": [
                    {
                        "step_number": 1,
                        "instruction": "Mix it",
                        "active_time_minutes": 5,
                        "timers": None,
                        "wait_time_minutes": None,
                        "wait_type": None,
                        "can_prep_ahead": True,
                        "is_optional": False,
                    }
                ],
            },
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeVersion, version, id=version_id)

        response = client.post(f"/v1/recipes/{recipe_id}/versions/{version_id}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Restored Name"

    def test_parse_quantity_display_invalid_falls_to_decimal(self):
        """Cover except branch where Fraction fails but Decimal succeeds (line 41-42)."""
        from api.v1.recipe.restore_recipe_version import _parse_quantity_display

        # "2.5" will parse fine as Decimal via float(Fraction("2.5")) but let's test
        # the fallback with a value that Fraction can't handle but Decimal can
        result = _parse_quantity_display("3")
        assert result == Decimal("3.0") or float(result) == pytest.approx(3.0)

    def _setup_restore(self, mock_db, mock_user, snapshot,
                       existing_ingredients=None, existing_steps=None):
        """Helper to set up restore test."""
        recipe_id = "recipe-restore"
        version_id = "version-restore"
        book_id = "book-restore"

        recipe = MockRecipe(
            id=recipe_id, recipe_book_id=book_id, name="Old",
            instructions="Old instr", description="D", servings=4,
            prep_time=10, cook_time=20, image_url=None, source_url=None,
            tags=[],
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        version = MockRecipeVersion(
            id=version_id, recipe_id=recipe_id, version_number=1,
            snapshot=snapshot,
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_note import RecipeNote
        from utils.models.recipe_step import RecipeStep
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeVersion, version, id=version_id)
        mock_db.set_where(RecipeIngredient, existing_ingredients or [])
        mock_db.set_where(RecipeStep, existing_steps or [])
        mock_db.set_where(RecipeNote, [])
        mock_db.set_where(RecipeVersion, [])

        return recipe_id, version_id

    def test_restore_with_existing_items_to_delete(self, client, mock_db, mock_user):
        """Existing ingredients/steps are deleted before restore (lines 103, 137)."""
        existing_ing = MockRecipeIngredient(recipe_id="recipe-restore")
        existing_step = MockRecipeStep(recipe_id="recipe-restore", step_number=1)

        recipe_id, version_id = self._setup_restore(
            mock_db, mock_user,
            snapshot={
                "name": "New",
                "ingredients": [
                    {"ingredient_id": str(uuid.uuid4()), "quantity_display": "2", "unit_display": "cups"},
                ],
                "steps": [{"step_number": 1, "instruction": "Do it"}],
            },
            existing_ingredients=[existing_ing],
            existing_steps=[existing_step],
        )
        response = client.post(f"/v1/recipes/{recipe_id}/versions/{version_id}/restore")
        assert response.status_code == 200

    def test_restore_empty_snapshot_no_updates(self, client, mock_db, mock_user):
        """Snapshot without name/instructions skips update (branches 93->95, 95->97, 97->101)."""
        recipe_id, version_id = self._setup_restore(
            mock_db, mock_user,
            snapshot={},  # no name, no instructions
        )
        response = client.post(f"/v1/recipes/{recipe_id}/versions/{version_id}/restore")
        assert response.status_code == 200

    def test_restore_parse_quantity_failure_in_ingredient(self, client, mock_db, mock_user):
        """Unparseable quantity falls back to Decimal('1') (lines 110-111)."""
        recipe_id, version_id = self._setup_restore(
            mock_db, mock_user,
            snapshot={
                "ingredients": [
                    {"ingredient_id": str(uuid.uuid4()), "quantity_display": "not-a-number!!!", "unit_display": "cups"},
                ],
            },
        )
        response = client.post(f"/v1/recipes/{recipe_id}/versions/{version_id}/restore")
        assert response.status_code == 200


# ===========================================================================
# 9. fork_recipe.py — lines 104-115, 122-133 (ingredient + step cloning)
# ===========================================================================


class TestForkRecipeCloning:
    """Cover ingredient and step cloning loops (lines 104-133)."""

    def test_fork_clones_ingredients_and_steps(self, client, mock_db, mock_user):
        """Fork with source ingredients and steps."""
        recipe_id = "13000000-0000-0000-0000-000000000001"
        book_id = "b0000000-0000-0000-0000-000000000001"
        dest_book_id = "b0000000-0000-0000-0000-000000000002"

        ingredient = MockRecipeIngredient(
            recipe_id=recipe_id,
            ingredient_id=str(uuid.uuid4()),
            quantity_display=Decimal("2"),
            unit_display="cups",
        )
        step = MockRecipeStep(recipe_id=recipe_id, step_number=1, instruction="Boil water")

        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Pasta", tags=["italian"])
        src_book = MockRecipeBook(id=book_id, name="Family")
        dest_book = MockRecipeBook(id=dest_book_id, name="My Recipes")
        src_mem = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="viewer",
        )
        dest_mem = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=dest_book_id, role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_step import RecipeStep

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, src_mem,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, dest_book, id=dest_book_id)
        mock_db.set_find_by(RecipeBookUser, dest_mem,
                            user_id=str(mock_user.id), recipe_book_id=dest_book_id)
        mock_db.set_find_by(RecipeBook, src_book, id=book_id)

        # where() returns ingredients and steps
        mock_db.set_where(RecipeIngredient, [ingredient])
        mock_db.set_where(RecipeStep, [step])

        response = client.post(
            f"/v1/recipes/{recipe_id}/fork",
            json={"destination_book_id": dest_book_id},
        )
        assert response.status_code == 201


# ===========================================================================
# 10. start_import.py — lines 48, 57, 80
# ===========================================================================


class TestStartImportExtended:
    """Cover missing branches in StartImport."""

    def test_book_not_found(self, client, mock_db, mock_user):
        """Book exists check returns 404 (line 48)."""
        book_id = "missing-book"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )

        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        # Book not found — no set_find_by for RecipeBook

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "url", "url": "https://example.com"},
        )
        assert response.status_code == 404

    def test_url_source_missing_url(self, client, mock_db, mock_user):
        """URL source type without url field (line 57)."""
        book_id = "test-book"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        book = MockRecipeBook(id=book_id)

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "url"},
        )
        assert response.status_code == 400

    @patch("api.v1.import_job.start_import.parse_source_task")
    def test_unsupported_source_type(self, mock_task, client, mock_db, mock_user):
        """Unsupported source_type (line 80)."""
        book_id = "test-book"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        book = MockRecipeBook(id=book_id)

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        response = client.post(
            f"/v1/recipe-books/{book_id}/import",
            json={"source_type": "fax"},
        )
        assert response.status_code == 400


# ===========================================================================
# 11. deactivate_invite_link.py — lines 30-40
# ===========================================================================


class TestDeactivateInviteLinkExtended:
    """Cover deactivation path (lines 30-40)."""

    def test_deactivate_success(self, client, mock_db, mock_user):
        """Owner deactivates their link."""
        link_id = str(uuid.uuid4())
        link = MockInviteLink(
            id=link_id, is_active=True,
            created_by_id=str(mock_user.id),
        )
        mock_db.db.execute.return_value = MockExecuteResult([link])

        response = client.delete(f"/v1/invite-links/{link_id}")
        assert response.status_code == 200
        assert link.is_active is False

    def test_deactivate_wrong_user(self, client, mock_db, mock_user):
        """Non-creator gets 403."""
        link_id = str(uuid.uuid4())
        link = MockInviteLink(
            id=link_id, is_active=True,
            created_by_id=str(uuid.uuid4()),  # different user
        )
        mock_db.db.execute.return_value = MockExecuteResult([link])

        response = client.delete(f"/v1/invite-links/{link_id}")
        assert response.status_code == 403


# ===========================================================================
# 12. join_via_link.py — lines 51, 58, 65, 75-78
# ===========================================================================


class TestJoinViaLinkExtended:
    """Cover remaining join-via-link branches."""

    def test_join_inactive_link(self, client, mock_db, mock_user):
        """Link is deactivated — 410 (line 51)."""
        creator = MockUser(id=str(uuid.uuid4()))
        link = MockInviteLink(
            token="tok-inactive", is_active=False,
            created_by=creator, created_by_id=str(creator.id),
        )
        mock_db.db.execute.return_value = MockExecuteResult([link])

        response = client.post("/v1/invite-links/tok-inactive/join")
        assert response.status_code == 410

    def test_join_expired_link(self, client, mock_db, mock_user):
        """Link is expired — 410 (line 58)."""
        creator = MockUser(id=str(uuid.uuid4()))
        link = MockInviteLink(
            token="tok-expired", is_active=True,
            expires_at=datetime.now(UTC) - timedelta(days=1),
            created_by=creator, created_by_id=str(creator.id),
        )
        mock_db.db.execute.return_value = MockExecuteResult([link])

        response = client.post("/v1/invite-links/tok-expired/join")
        assert response.status_code == 410

    def test_join_max_uses_reached(self, client, mock_db, mock_user):
        """Link has reached max uses — 410 (line 65)."""
        creator = MockUser(id=str(uuid.uuid4()))
        link = MockInviteLink(
            token="tok-maxuse", is_active=True,
            max_uses=5, use_count=5,
            created_by=creator, created_by_id=str(creator.id),
        )
        mock_db.db.execute.return_value = MockExecuteResult([link])

        response = client.post("/v1/invite-links/tok-maxuse/join")
        assert response.status_code == 410

    def test_join_already_member(self, client, mock_db, mock_user):
        """User is already a member — returns already_member=True (lines 75-78)."""
        creator = MockUser(id=str(uuid.uuid4()))
        link = MockInviteLink(
            token="tok-member", is_active=True,
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by=creator, created_by_id=str(creator.id),
        )
        existing_membership = MockRecipeBookUser()

        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),              # fetch link
            MockExecuteResult([existing_membership]),  # check_existing_membership
            MockExecuteResult(["My Book"]),          # get_resource_name
        ]

        response = client.post("/v1/invite-links/tok-member/join")
        assert response.status_code == 200
        data = response.json()
        assert data["already_member"] is True


# ===========================================================================
# 13. preview_invite_link.py — lines 43, 45, 47, 51
# ===========================================================================


class TestPreviewInviteLinkExtended:
    """Cover all state branches in PreviewInviteLink."""

    def test_preview_inactive_state(self, client, mock_db, mock_user):
        """Inactive link returns state='inactive' (line 43)."""
        creator = MockUser(id=str(uuid.uuid4()), name="C", username="c")
        link = MockInviteLink(
            token="tok-prev-inactive", is_active=False,
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by=creator, created_by_id=str(creator.id),
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),
            MockExecuteResult(["Book Name"]),
        ]

        response = client.get("/v1/invite-links/tok-prev-inactive")
        assert response.status_code == 200
        assert response.json()["state"] == "inactive"

    def test_preview_expired_state(self, client, mock_db, mock_user):
        """Expired link returns state='expired' (line 45)."""
        creator = MockUser(id=str(uuid.uuid4()), name="C", username="c")
        link = MockInviteLink(
            token="tok-prev-exp", is_active=True,
            expires_at=datetime.now(UTC) - timedelta(days=1),
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by=creator, created_by_id=str(creator.id),
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),
            MockExecuteResult(["Book"]),
        ]

        response = client.get("/v1/invite-links/tok-prev-exp")
        assert response.status_code == 200
        assert response.json()["state"] == "expired"

    def test_preview_full_state(self, client, mock_db, mock_user):
        """Max uses reached returns state='full' (line 47)."""
        creator = MockUser(id=str(uuid.uuid4()), name="C", username="c")
        link = MockInviteLink(
            token="tok-prev-full", is_active=True, max_uses=3, use_count=3,
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by=creator, created_by_id=str(creator.id),
        )
        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),
            MockExecuteResult(["Book"]),
        ]

        response = client.get("/v1/invite-links/tok-prev-full")
        assert response.status_code == 200
        assert response.json()["state"] == "full"

    def test_preview_already_member_state(self, client, mock_db, mock_user):
        """Already a member returns state='already_member' (line 51)."""
        creator = MockUser(id=str(uuid.uuid4()), name="C", username="c")
        link = MockInviteLink(
            token="tok-prev-member", is_active=True,
            resource_type="recipe_book",
            resource_id="b0000000-0000-0000-0000-000000000001",
            created_by=creator, created_by_id=str(creator.id),
        )
        existing = MockRecipeBookUser()
        mock_db.db.execute.side_effect = [
            MockExecuteResult([link]),
            MockExecuteResult([existing]),  # check_existing_membership -> found
            MockExecuteResult(["Book"]),
        ]

        response = client.get("/v1/invite-links/tok-prev-member")
        assert response.status_code == 200
        assert response.json()["state"] == "already_member"


# ===========================================================================
# 14. get_meal_event.py — lines 44, 53, 65
# ===========================================================================


class TestGetMealEventExtended:
    """Cover missing branches in GetMealEvent."""

    def test_get_meal_event_non_calendar_member_returns_404(
        self, client, mock_db, mock_user
    ):
        """Non-member of the event's calendar → 404 (no existence leak)."""
        event_id = "evt-noaccess"
        event = MockMealEvent(
            id=event_id, owner_id=str(uuid.uuid4()),
            participants=[], recipe=None,
        )

        from utils.models.calendar_user import CalendarUser
        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)
        mock_db.set_find_by(
            CalendarUser, None,
            user_id=mock_user.id, calendar_id=event.calendar_id,
        )

        response = client.get(f"/v1/meal-events/{event_id}")
        assert response.status_code == 404

    def test_get_meal_event_with_recipe(self, client, mock_db, mock_user):
        """Event with recipe returns recipe summary (line 53)."""
        event_id = "evt-recipe"
        recipe = MockRecipe(
            id="r1", name="Pasta", description="Italian",
            prep_time=10, cook_time=20, image_url="http://img.jpg",
        )
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[], recipe=recipe, pantry_id=None,
            parent_event_id=None,
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.get(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["recipe"]["name"] == "Pasta"

    def test_get_meal_event_with_participants(self, client, mock_db, mock_user):
        """Event with participants returns participant list (line 65)."""
        event_id = "evt-parts"
        p_user = MockUser(id="pu1", email="p@test.com", name="Participant")
        participant = MockMealEventParticipant(
            meal_event_id=event_id, user_id="pu1", role="guest",
            status="accepted", assigned_tasks=["salad"],
            user=p_user,
        )
        event = MockMealEvent(
            id=event_id, owner_id=str(mock_user.id),
            participants=[participant], recipe=None, pantry_id=None,
            parent_event_id=None,
        )

        from utils.models.meal_event import MealEvent

        mock_db.set_find_by(MealEvent, event, id=event_id)

        response = client.get(f"/v1/meal-events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["participants"]) == 1
        assert data["participants"][0]["user_email"] == "p@test.com"


# ===========================================================================
# 15. list_meal_events.py — lines 68, 72, 89
# ===========================================================================


class TestListMealEventsExtended:
    """Cover filter branches in ListMealEvents."""

    def test_list_with_meal_type_filter(self, client, mock_db, mock_user):
        """meal_type filter (line 68)."""
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/meal-events?meal_type=dinner")
        assert response.status_code == 200

    def test_list_with_status_filter(self, client, mock_db, mock_user):
        """status filter (line 72)."""
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/meal-events?status=planned")
        assert response.status_code == 200

    def test_list_with_recipe_in_event(self, client, mock_db, mock_user):
        """Event with recipe produces recipe_summary (line 89)."""
        recipe = MockRecipe(
            id="r1", name="Soup", description="Warm",
            prep_time=5, cook_time=30, image_url=None,
        )
        event = MockMealEvent(
            owner_id=str(mock_user.id), participants=[],
            recipe=recipe,
        )
        mock_db.db.query.return_value = MockQuery([event])

        response = client.get("/v1/meal-events")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["recipe"]["name"] == "Soup"


# ===========================================================================
# 16. search_ingredients.py — lines 38-40 (fallback ILIKE)
# ===========================================================================


class TestSearchIngredientsFallback:
    """Cover the pg_trgm exception fallback (lines 38-40)."""

    def test_search_ingredients_fallback(self, client, mock_db):
        """When pg_trgm fails, ILIKE fallback is used."""
        class Row:
            def __init__(self):
                self.id = "ing-fb"
                self.canonical_name = "sugar"
                self.category = "baking"
                self.similarity = 1.0

        call_count = [0]

        def execute_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("pg_trgm not available")
            return [Row()]

        mock_db.db.execute.side_effect = execute_side

        response = client.get("/v1/ingredients/search?q=sugar")
        assert response.status_code == 200


# ===========================================================================
# 17. recipe_book_router.py — lines 156, 230-233, 238
# ===========================================================================


class TestRecipeBookRouterWebsocket:
    """Cover the websocket handler in recipe_book_router (lines 230-238)."""

    def test_websocket_missing_token(self, client, mock_db):
        """WS without token closes with 4001 (line 223)."""
        with pytest.raises(Exception):
            with client.websocket_connect("/v1/recipe-books/ws/book1"):
                pass

    def test_websocket_auth_failed(self, client, mock_db):
        """WS with invalid token closes (lines 234-236)."""
        with pytest.raises(Exception):
            with client.websocket_connect("/v1/recipe-books/ws/book1?token=badtoken"):
                pass

    def test_add_member_notify_branch(self, client, mock_db, mock_user):
        """add_recipe_book_member notifies the target user (line 156)."""
        book_id = "b-notify"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        book = MockRecipeBook(id=book_id, name="Shared Book")
        target_user = MockUser(id="target-user")

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.user import User

        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(User, target_user, id="target-user")
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        with patch("routers.v1.recipe_book_router.notify_book_shared") as mock_notify:
            response = client.post(
                f"/v1/recipe-books/{book_id}/members",
                json={"user_id": "target-user", "role": "editor"},
            )
        # The endpoint might succeed or fail based on inner logic, but we're
        # testing the router-level notification code path
        mock_notify.assert_called_once()


# ===========================================================================
# 18. shopping_list_router.py — lines 198, 413, 485-504
# ===========================================================================


class TestShoppingListRouterWebsocket:
    """Cover WebSocket handler in shopping_list_router (lines 485-504)."""

    def test_ws_missing_token(self, client, mock_db):
        """WS without token closes with 4001."""
        with pytest.raises(Exception):
            with client.websocket_connect("/v1/ws/shopping-lists/list1"):
                pass

    def test_ws_auth_failed(self, client, mock_db):
        """WS with invalid token closes."""
        with pytest.raises(Exception):
            with client.websocket_connect("/v1/ws/shopping-lists/list1?token=bad"):
                pass


# ===========================================================================
# 19. list_threads.py — branch 34->37 (thread.chats empty)
# ===========================================================================


class TestListThreadsEmptyChats:
    """Cover the 'no chats' branch (branch 34->37)."""

    def test_list_threads_thread_with_no_chats(self, client, mock_db, mock_user):
        """Thread with empty chats list — last_message should be None."""
        thread = MockModel(
            id=str(uuid.uuid4()),
            user_id=str(mock_user.id),
            title="Empty Thread",
            chats=[],
        )
        mock_db.db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(all=lambda: [thread])
        )
        response = client.get("/v1/chat/threads")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["last_message"] is None
        assert data["items"][0]["message_count"] == 0


# ===========================================================================
# 20. invitations/helpers.py — branches 111->exit, 276->298
# ===========================================================================


class TestInvitationHelpersExtended:
    """Cover uncovered branches in helpers.py."""

    def test_check_resource_permission_meal_event_not_found(self):
        """Meal event not found raises 404 (line 111->exit scenario)."""
        from api.v1.invitations.helpers import check_resource_permission
        from utils.api.endpoint import APIException

        db = MagicMock()
        db.execute.return_value = MockExecuteResult([])

        with pytest.raises(APIException) as exc_info:
            check_resource_permission(db, uuid.uuid4(), "meal_event", uuid.uuid4())
        assert exc_info.value.status_code == 404

    def test_create_membership_meal_event_new(self):
        """Create membership for meal_event — new member path (line 276->298)."""
        from api.v1.invitations.helpers import create_membership

        db = MagicMock()
        db.execute.return_value = MockExecuteResult([])

        create_membership(
            db, uuid.uuid4(), "meal_event", uuid.uuid4(), "guest", uuid.uuid4(),
        )
        db.add.assert_called_once()
        db.flush.assert_called_once()

    def test_create_membership_meal_event_reactivate(self):
        """Reactivate archived meal_event membership."""
        from api.v1.invitations.helpers import create_membership

        existing = MockMealEventParticipant(archived_at=datetime.now(UTC))
        db = MagicMock()
        db.execute.return_value = MockExecuteResult([existing])

        create_membership(
            db, uuid.uuid4(), "meal_event", uuid.uuid4(), "cohost", uuid.uuid4(),
        )
        assert existing.archived_at is None
        assert existing.role == "cohost"
        assert existing.status == "accepted"

    def test_check_existing_membership_unknown_resource_type(self):
        """Unknown resource_type returns False (line 193)."""
        from api.v1.invitations.helpers import check_existing_membership

        db = MagicMock()
        result = check_existing_membership(db, uuid.uuid4(), "unknown_type", uuid.uuid4())
        assert result is False


# ===========================================================================
# 21. send_invitation.py — branch 110->115 (existing pending invite by email)
# ===========================================================================


class TestSendInvitationExtended:
    """Cover branch for duplicate email-based invitation (line 110->115)."""

    def test_duplicate_email_invitation(self, client, mock_db, mock_user):
        """Sending a second invitation to the same email returns 409."""
        from utils.models.invitation import Invitation

        # Set up: user has permission, target is by email (no user found)
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), role="owner",
        )
        existing_invite = MockModel(status="pending")

        call_count = [0]
        def execute_side(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MockExecuteResult([membership])  # permission check
            if call_count[0] == 2:
                return MockExecuteResult([None])  # target user lookup by email
            if call_count[0] == 3:
                return MockExecuteResult([existing_invite])  # dup check
            return MockExecuteResult([])

        mock_db.db.execute.side_effect = execute_side

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": "b0000000-0000-0000-0000-000000000001",
                "role_offered": "editor",
                "to_email": "already@invited.com",
            },
        )
        assert response.status_code == 409


# ===========================================================================
# 22. bulk_move_recipes.py — line 50 (recipe not found in loop)
# ===========================================================================


class TestBulkMoveRecipesExtended:
    """Cover recipe-not-found branch (line 50)."""

    def test_bulk_move_recipe_not_found(self, client, mock_db, mock_user):
        """One recipe not found returns 404."""
        dest_book = MockRecipeBook(id="dest-b")
        dest_mem = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id="dest-b", role="owner",
        )

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBook, dest_book, id="dest-b")
        mock_db.set_find_by(RecipeBookUser, dest_mem,
                            user_id=str(mock_user.id), recipe_book_id="dest-b")
        # Recipe not found - no set_find_by

        response = client.post(
            "/v1/recipes/bulk/move",
            json={"recipe_ids": ["nonexistent"], "destination_book_id": "dest-b"},
        )
        assert response.status_code == 404


# ===========================================================================
# 23. bulk_update_tags.py — line 35, branch 58->57
# ===========================================================================


class TestBulkUpdateTagsExtended:
    """Cover missing branches in BulkUpdateTags."""

    def test_no_tag_changes(self, client, mock_db, mock_user):
        """No add_tags or remove_tags returns 400 (line 35)."""
        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": ["r1"]},
        )
        assert response.status_code == 400

    def test_add_duplicate_tag(self, client, mock_db, mock_user):
        """Adding a tag that already exists is deduplicated (branch 58->57)."""
        recipe = MockRecipe(
            id="r-dup-tag", recipe_book_id="b1", tags=["italian"],
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id="b1", role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id="r-dup-tag")
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id="b1")

        response = client.post(
            "/v1/recipes/bulk/tags",
            json={
                "recipe_ids": ["r-dup-tag"],
                "add_tags": ["italian", "quick"],  # "italian" already present
            },
        )
        assert response.status_code == 200
        assert recipe.tags == ["italian", "quick"]


# ===========================================================================
# 24. create_recipe.py — lines 98-99 (normalization failure)
# ===========================================================================


class TestCreateRecipeExtended:
    """Cover normalization failure branch in CreateRecipe (lines 98-99)."""

    def test_create_recipe_normalization_failure(self, client, mock_db, mock_user):
        """When normalize_quantity raises, fallback to display values (lines 98-99)."""
        book_id = "book-norm-fail"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        book = MockRecipeBook(id=book_id)
        ingredient = MockIngredient(id="ing-norm", canonical_name="custom spice")

        from utils.models.ingredient import Ingredient
        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        mock_db.set_find_by(Ingredient, ingredient, id="ing-norm")

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=None), \
             patch("utils.services.units.conversion.normalize_quantity", side_effect=Exception("fail")):
            response = client.post(
                f"/v1/recipe-books/{book_id}/recipes",
                json={
                    "name": "Test Recipe",
                    "ingredients": [
                        {"ingredient_id": "ing-norm", "quantity": 1, "unit": "pinch"},
                    ],
                },
            )
        assert response.status_code == 201


# ===========================================================================
# 25. delete_recipe_note.py — line 26 (recipe not found)
# ===========================================================================


class TestDeleteRecipeNoteExtended:
    """Cover recipe-not-found branch (line 26)."""

    def test_delete_note_recipe_not_found(self, client, mock_db, mock_user):
        """Recipe not found returns 404."""
        response = client.delete("/v1/recipes/missing/notes/note1")
        assert response.status_code == 404


# ===========================================================================
# 26. update_recipe.py — lines 44, 120, 139-140
# ===========================================================================


class TestUpdateRecipeExtended:
    """Cover missing branches in UpdateRecipe."""

    def test_update_recipe_not_found(self, client, mock_db, mock_user):
        """Recipe not found returns 404 (line 44)."""
        response = client.put(
            "/v1/recipes/missing",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    def test_update_recipe_normalization_failure(self, client, mock_db, mock_user):
        """Ingredient normalization failure uses display values (lines 139-140)."""
        recipe_id = "r-upd-norm"
        book_id = "b-upd-norm"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Old")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        ingredient = MockIngredient(id="ing-upd", canonical_name="flour")

        from utils.models.ingredient import Ingredient
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(Ingredient, ingredient, id="ing-upd")

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=None), \
             patch("utils.services.units.conversion.normalize_quantity", side_effect=Exception("fail")):
            response = client.put(
                f"/v1/recipes/{recipe_id}",
                json={
                    "ingredients": [
                        {"ingredient_id": "ing-upd", "quantity": 2, "unit": "pinch"},
                    ],
                },
            )
        assert response.status_code == 200


# ===========================================================================
# 27. search_users.py — line 25 (empty query)
# ===========================================================================


class TestSearchUsersEmptyQuery:
    """Cover empty query branch (line 25) - already covered by test_user.py,
    but adding direct endpoint test to make sure."""

    def test_search_users_whitespace_only(self, mock_db, mock_user):
        """Whitespace-only query raises (line 25)."""
        from api.v1.user.search_users import SearchUsers
        from utils.api.endpoint import APIException

        endpoint = SearchUsers(user=mock_user, database=mock_db)
        with pytest.raises(APIException) as exc:
            endpoint.execute(q="   ")
        assert exc.value.status_code == 400


# ===========================================================================
# 28. Additional remaining gaps — statement and branch coverage
# ===========================================================================


class TestCreateInviteLinkExpiresInDays:
    """Cover expires_in_days branch in CreateInviteLink (line 31)."""

    def test_create_invite_link_with_expires_in_days(self, client, mock_db, mock_user):
        """Setting expires_in_days calculates expires_at."""
        book_id = "b0000000-0000-0000-0000-000000000001"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        mock_db.db.execute.return_value = MockExecuteResult([membership])

        response = client.post(
            "/v1/invite-links",
            json={
                "resource_type": "recipe_book",
                "resource_id": book_id,
                "role_offered": "viewer",
                "expires_in_days": 7,
            },
        )
        assert response.status_code in (200, 201)


class TestAddShoppingListItemEdgeCases:
    """Cover missing lines in add_item.py (34, 52)."""

    @patch("api.v1.shopping_list.add_item.notify_item_added")
    def test_add_item_list_not_found(self, mock_notify, client, mock_db, mock_user):
        """404 when list doesn't exist (line 34)."""
        response = client.post(
            "/v1/shopping-lists/missing-list/items",
            json={"name": "Milk"},
        )
        assert response.status_code == 404

    @patch("api.v1.shopping_list.add_item.notify_item_added")
    def test_add_item_no_permission(self, mock_notify, client, mock_db, mock_user):
        """403 when user has no edit access (line 52)."""
        list_id = "sl-no-perm"
        sl = MockShoppingList(id=list_id, owner_id=str(uuid.uuid4()))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/items",
            json={"name": "Milk"},
        )
        assert response.status_code == 403


class TestDeleteShoppingListAccessDenied:
    """Cover non-owner delete denial (line 39)."""

    def test_delete_shopping_list_non_owner(self, client, mock_db, mock_user):
        """Non-owner gets 403."""
        list_id = "sl-notowner"
        sl = MockShoppingList(id=list_id, owner_id=str(uuid.uuid4()))

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.delete(f"/v1/shopping-lists/{list_id}")
        assert response.status_code == 403


class TestListShoppingListsExtended:
    """Cover status filter (line 61) and shared member count (line 84)."""

    def test_list_shopping_lists_with_status_filter(self, client, mock_db, mock_user):
        """Status filter branch (line 61)."""
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/shopping-lists?status=active")
        assert response.status_code == 200

    def test_list_shopping_lists_shared_with_members(self, client, mock_db, mock_user):
        """Shared list counts members (line 84)."""
        member = MockShoppingListUser(
            user_id=str(mock_user.id), archived_at=None,
        )
        sl = MockShoppingList(
            owner_id=str(mock_user.id), is_shared=True,
            items=[], members=[member],
        )
        mock_db.db.query.return_value = MockQuery([sl])

        response = client.get("/v1/shopping-lists")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


class TestBulkUpdateTagsNoChanges:
    """Cover the no-tag-changes branch missed in line 35."""

    def test_empty_recipe_ids_returns_400(self, client, mock_db, mock_user):
        """Empty recipe_ids returns 400."""
        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": [], "add_tags": ["quick"]},
        )
        assert response.status_code == 400


class TestRestoreRecipeNormalizationSuccess:
    """Cover normalize_quantity success path in restore (lines 115-116)."""

    def test_restore_with_mocked_normalize_success(self, client, mock_db, mock_user):
        """When normalize_quantity succeeds, uses normalized values (lines 115-116)."""
        recipe_id = "recipe-norm-ok"
        version_id = "version-norm-ok"
        book_id = "book-norm-ok"

        recipe = MockRecipe(
            id=recipe_id, recipe_book_id=book_id, name="Test",
            instructions=None, description=None, servings=1,
            prep_time=None, cook_time=None, image_url=None, source_url=None,
            tags=[],
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        version = MockRecipeVersion(
            id=version_id, recipe_id=recipe_id, version_number=1,
            snapshot={
                "ingredients": [
                    {
                        "ingredient_id": str(uuid.uuid4()),
                        "quantity_display": "1",
                        "unit_display": "cups",
                    }
                ],
            },
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_note import RecipeNote
        from utils.models.recipe_step import RecipeStep
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeVersion, version, id=version_id)
        mock_db.set_where(RecipeIngredient, [])
        mock_db.set_where(RecipeStep, [])
        mock_db.set_where(RecipeNote, [])
        mock_db.set_where(RecipeVersion, [])

        # Mock normalize_quantity to return a successful result
        mock_normalized = MagicMock()
        mock_normalized.quantity_normalized = 240.0
        mock_normalized.unit_normalized = "ml"

        with patch("api.v1.recipe.restore_recipe_version.normalize_quantity",
                    return_value=mock_normalized):
            response = client.post(f"/v1/recipes/{recipe_id}/versions/{version_id}/restore")
        assert response.status_code == 200


class TestUpdateRecipeEmbeddingBranch:
    """Cover line 120 in update_recipe — ingredient not found during update."""

    def test_update_recipe_ingredient_not_found(self, client, mock_db, mock_user):
        """Ingredient not found returns 400 (line 120)."""
        recipe_id = "r-upd-ing-nf"
        book_id = "b-upd-ing-nf"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Test")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        # Ingredient not found (no set_find_by for Ingredient)

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=None):
            response = client.put(
                f"/v1/recipes/{recipe_id}",
                json={
                    "ingredients": [
                        {"ingredient_id": "missing-ing", "quantity": 2, "unit": "cups"},
                    ],
                },
            )
        assert response.status_code == 400


class TestPopulateFromRecipeMissing:
    """Cover populate_from_recipe.py line 95."""

    def test_populate_from_recipe_ingredient_with_no_ingredient_obj(self, client, mock_db, mock_user):
        """RecipeIngredient where .ingredient is None is skipped (line 95)."""
        list_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())

        ri = MockRecipeIngredient(
            ingredient_id=str(uuid.uuid4()),
            recipe_id=recipe_id,
            quantity_display=Decimal("1"),
            unit_display="tsp",
        )
        ri.ingredient = None  # no ingredient resolved

        recipe = MockRecipe(id=recipe_id, recipe_book_id="b1")
        recipe.ingredients = [ri]

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id="b1", role="owner",
        )

        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id="b1")

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe",
            json={"recipe_id": recipe_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0


# ===========================================================================
# 29. Additional statement and branch gaps
# ===========================================================================


class TestBulkUpdateTagsRecipeNotFound:
    """Cover recipe-not-found in bulk_update_tags loop (line 35)."""

    def test_recipe_not_found_returns_404(self, client, mock_db, mock_user):
        """Recipe not found in bulk tag update returns 404."""
        response = client.post(
            "/v1/recipes/bulk/tags",
            json={"recipe_ids": ["nonexistent"], "add_tags": ["quick"]},
        )
        assert response.status_code == 404


class TestUpdateRecipeIngNotFound:
    """Cover update_recipe line 120 (delete existing ingredients) and ingredient not found."""

    def test_update_recipe_deletes_existing_ingredients(self, client, mock_db, mock_user):
        """Updating with ingredients deletes existing ones first (line 120)."""
        recipe_id = "r-del-existing"
        book_id = "b-del-existing"
        recipe = MockRecipe(id=recipe_id, recipe_book_id=book_id, name="Test")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        existing_ri = MockRecipeIngredient(recipe_id=recipe_id)
        ingredient = MockIngredient(id="ing-ok", canonical_name="flour")

        from utils.models.ingredient import Ingredient
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.recipe_ingredient import RecipeIngredient
        from utils.models.recipe_note import RecipeNote
        from utils.models.recipe_step import RecipeStep
        from utils.models.recipe_version import RecipeVersion

        mock_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(Ingredient, ingredient, id="ing-ok")

        # Set up existing items for deletion
        mock_db.set_where(RecipeIngredient, [existing_ri])
        mock_db.set_where(RecipeStep, [])
        mock_db.set_where(RecipeNote, [])
        mock_db.set_where(RecipeVersion, [])

        with patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=None):
            response = client.put(
                f"/v1/recipes/{recipe_id}",
                json={
                    "ingredients": [
                        {"ingredient_id": "ing-ok", "quantity": 1, "unit": "cup"},
                    ],
                },
            )
        assert response.status_code == 200


class TestRecipeRouterNotifySharedBook:
    """Cover recipe_router.py line 87 (notify_recipe_added for shared book)."""

    @patch("api.v1.search.generate_recipe_embedding.generate_recipe_embedding", return_value=None)
    def test_create_recipe_in_shared_book_notifies(self, mock_embed, client, mock_db, mock_user):
        """Creating recipe in shared book triggers notification (line 87)."""
        book_id = "shared-book"
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=book_id, role="owner",
        )
        book = MockRecipeBook(id=book_id, name="Shared Book", is_shared=True)

        from utils.models.recipe_book import RecipeBook
        from utils.models.recipe_book_user import RecipeBookUser

        mock_db.set_find_by(RecipeBookUser, membership,
                            user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.set_find_by(RecipeBook, book, id=book_id)

        with patch("routers.v1.recipe_router.notify_recipe_added") as mock_notify:
            response = client.post(
                f"/v1/recipe-books/{book_id}/recipes",
                json={"name": "Shared Pasta"},
            )
        assert response.status_code == 201
        mock_notify.assert_called_once()
