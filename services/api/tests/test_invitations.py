"""Tests for invitation endpoints."""

import uuid
from datetime import UTC, datetime, timedelta

from conftest import (
    MockExecuteResult,
    MockInvitation,
    MockMealEvent,
    MockMealEventParticipant,
    MockModel,
    MockRecipeBookUser,
    MockShoppingList,
    MockShoppingListUser,
    MockUser,
)


BOOK_ID = "b0000000-0000-0000-0000-000000000001"
PANTRY_ID = "c0000000-0000-0000-0000-000000000001"
SHOPPING_LIST_ID = "d0000000-0000-0000-0000-000000000001"
MEAL_EVENT_ID = "e0000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# helpers — MockPantryUser (not in conftest, use MockModel directly)
# ---------------------------------------------------------------------------


class MockPantryUser(MockModel):
    """Mock PantryUser model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "pantry_id": str(uuid.uuid4()),
            "role": "owner",
            "invited_by_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockPantry(MockModel):
    """Mock Pantry model."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Test Pantry",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


# ===================================================================
# TestListReceivedInvitations
# ===================================================================


class TestListReceivedInvitations:
    """Tests for GET /v1/invitations."""

    def test_list_received_invitations_empty(self, client, mock_async_db, mock_user):
        """Listing returns empty list when no invitations exist."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/invitations")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_returns_invitation_items(self, client, mock_async_db, mock_user):
        """GET /v1/invitations returns invitation items with from_user info."""
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice", username="alice")
        invitation = MockInvitation(
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),   # fetch invitations list
            MockExecuteResult(["My Book"]),    # get_resource_name
        ]

        response = client.get("/v1/invitations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["role_offered"] == "editor"
        assert data[0]["from_user"]["name"] == "Alice"
        assert data[0]["resource_name"] == "My Book"

    def test_list_received_skips_expired(self, client, mock_async_db, mock_user):
        """Expired invitations are filtered out of the received list."""
        from_user = MockUser(id=str(uuid.uuid4()), name="Bob", username="bob")
        expired_inv = MockInvitation(
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="viewer",
            status="pending",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        expired_inv.from_user = from_user

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([expired_inv]),  # fetch invitations list
        ]

        response = client.get("/v1/invitations")
        assert response.status_code == 200
        assert response.json() == []


# ===================================================================
# TestListSentInvitations
# ===================================================================


class TestListSentInvitations:
    """Tests for GET /v1/invitations/sent."""

    def test_list_sent_invitations_empty(self, client, mock_async_db, mock_user):
        """Empty sent list returns 200 with no items."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_sent_with_to_user(self, client, mock_async_db, mock_user):
        """Sent invitation with a resolved to_user returns user info."""
        to_user = MockUser(
            id=str(uuid.uuid4()), name="Jane", username="jane", picture="pic.jpg"
        )
        invitation = MockInvitation(
            from_user_id=mock_user.id,
            to_user_id=to_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            message="Please join!",
        )
        invitation.to_user = to_user

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),  # fetch sent invitations
            MockExecuteResult(["My Book"]),   # get_resource_name (recipe_book)
        ]

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["to_user"]["name"] == "Jane"
        assert data[0]["to_user"]["picture"] == "pic.jpg"
        assert data[0]["resource_name"] == "My Book"
        assert data[0]["message"] == "Please join!"

    def test_list_sent_without_to_user(self, client, mock_async_db, mock_user):
        """Sent invitation with no resolved to_user returns to_user as null."""
        invitation = MockInvitation(
            from_user_id=mock_user.id,
            to_user_id=None,
            to_email="unknown@example.com",
            resource_type="pantry",
            resource_id=PANTRY_ID,
            role_offered="editor",
            status="pending",
        )
        invitation.to_user = None

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),     # fetch sent invitations
            MockExecuteResult(["My Pantry"]),    # get_resource_name (pantry)
        ]

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["to_user"] is None
        assert data[0]["to_email"] == "unknown@example.com"
        assert data[0]["resource_name"] == "My Pantry"

    def test_list_sent_shopping_list_resource_name(self, client, mock_async_db, mock_user):
        """get_resource_name for shopping_list returns name or fallback."""
        invitation = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="shopping_list",
            resource_id=SHOPPING_LIST_ID,
            role_offered="editor",
            status="pending",
        )
        invitation.to_user = None

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),    # fetch sent invitations
            MockExecuteResult([None]),          # get_resource_name → sl name is None
        ]

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        data = response.json()
        # When shopping list name is None, fallback is "Shopping List"
        assert data[0]["resource_name"] == "Shopping List"

    def test_list_sent_shopping_list_with_name(self, client, mock_async_db, mock_user):
        """get_resource_name for shopping_list with a real name."""
        invitation = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="shopping_list",
            resource_id=SHOPPING_LIST_ID,
            role_offered="editor",
            status="pending",
        )
        invitation.to_user = None

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),         # fetch sent invitations
            MockExecuteResult(["Weekly Groceries"]), # get_resource_name
        ]

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] == "Weekly Groceries"

    def test_list_sent_meal_event_resource_name(self, client, mock_async_db, mock_user):
        """get_resource_name for meal_event returns the title."""
        invitation = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="meal_event",
            resource_id=MEAL_EVENT_ID,
            role_offered="guest",
            status="pending",
        )
        invitation.to_user = None

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),        # fetch sent invitations
            MockExecuteResult(["Friday Dinner"]),   # get_resource_name
        ]

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] == "Friday Dinner"

    def test_list_sent_unknown_resource_type(self, client, mock_async_db, mock_user):
        """get_resource_name for unknown resource_type returns None."""
        invitation = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="unknown_type",
            resource_id=str(uuid.uuid4()),
            role_offered="editor",
            status="pending",
        )
        invitation.to_user = None

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),  # fetch sent invitations
            # get_resource_name for unknown type doesn't do a query — returns None
        ]

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] is None

    def test_list_sent_resource_not_found(self, client, mock_async_db, mock_user):
        """get_resource_name returns None when resource doesn't exist."""
        invitation = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="accepted",
        )
        invitation.to_user = None

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),   # fetch sent invitations
            MockExecuteResult([]),             # get_resource_name → no recipe book found
        ]

        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] is None


# ===================================================================
# TestSendInvitation
# ===================================================================


class TestSendInvitation:
    """Tests for POST /v1/invitations."""

    def test_send_invitation_missing_fields(self, client, mock_async_db, mock_user):
        """Sending an invitation with missing required fields fails with 422."""
        response = client.post("/v1/invitations", json={})
        assert response.status_code == 422

    def test_send_invitation_no_permission_returns_403(self, client, mock_async_db, mock_user):
        """Sender without membership on the recipe book gets 403."""
        # check_resource_permission -> db.execute returns no membership
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "someuser",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_self_invite_returns_400(self, client, mock_async_db, mock_user):
        """Inviting yourself returns 400."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        # sequence: 1=check_resource_permission, 2=username lookup -> same as mock_user
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),  # check_resource_permission
            MockExecuteResult([mock_user]),   # User lookup by username -> self
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": mock_user.username,
            },
        )
        assert response.status_code == 400

    def test_send_invitation_to_username_success(self, client, mock_async_db, mock_user):
        """Owner can send invitation by username -- returns 201 with pending status."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="janesmith")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        # Sequence of db.execute() calls in SendInvitation.execute():
        # 1. check_resource_permission: RecipeBookUser lookup
        # 2. User lookup by username
        # 3. check_existing_membership: RecipeBookUser lookup
        # 4. duplicate invitation check
        # 5. rate limit count (scalar)
        # 6. get_resource_name: RecipeBook.name (called in push notification block)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),   # check_resource_permission
            MockExecuteResult([target_user]),  # User lookup by username
            MockExecuteResult([]),             # check_existing_membership -> not a member
            MockExecuteResult([]),             # duplicate invitation check -> none
            MockExecuteResult([0]),            # rate limit count -> 0 sent today
            MockExecuteResult(["My Book"]),    # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "janesmith",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["role_offered"] == "editor"

    def test_send_invitation_to_username_with_at_prefix(self, client, mock_async_db, mock_user):
        """Username with @ prefix is stripped and resolved."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="janesmith")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),   # check_resource_permission
            MockExecuteResult([target_user]),  # User lookup by username (after @ strip)
            MockExecuteResult([]),             # check_existing_membership
            MockExecuteResult([]),             # duplicate invitation check
            MockExecuteResult([0]),            # rate limit count
            MockExecuteResult(["My Book"]),    # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "@janesmith",
            },
        )
        assert response.status_code == 201

    def test_send_invitation_to_user_id_success(self, client, mock_async_db, mock_user):
        """Send invitation by to_user_id resolves the target user."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Jane", username="jane")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),    # check_resource_permission
            MockExecuteResult([target_user]),   # User lookup by id
            MockExecuteResult([]),              # check_existing_membership
            MockExecuteResult([]),              # duplicate invitation check
            MockExecuteResult([0]),             # rate limit count
            MockExecuteResult(["My Book"]),     # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_user_id": target_user.id,
            },
        )
        assert response.status_code == 201

    def test_send_invitation_invalid_resource_type(self, client, mock_async_db, mock_user):
        """Invalid resource_type returns 400."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "invalid_type",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 400

    def test_send_invitation_invalid_role_for_resource(self, client, mock_async_db, mock_user):
        """Invalid role for a valid resource_type returns 400."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "guest",  # guest is for meal_event, not recipe_book
                "to_username": "someone",
            },
        )
        assert response.status_code == 400

    def test_send_invitation_meal_event_valid_role(self, client, mock_async_db, mock_user):
        """meal_event with cohost/guest role passes validation."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "editor",  # invalid for meal_event
                "to_username": "someone",
            },
        )
        assert response.status_code == 400

    def test_send_invitation_no_target(self, client, mock_async_db, mock_user):
        """Omitting all target fields (to_user_id, to_username, to_email) returns 400."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="owner",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),  # check_resource_permission
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
            },
        )
        assert response.status_code == 400

    def test_send_invitation_pantry_permission_denied(self, client, mock_async_db, mock_user):
        """Sending invitation to pantry without permission returns 403."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "pantry",
                "resource_id": PANTRY_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_pantry_viewer_role_denied(self, client, mock_async_db, mock_user):
        """Pantry viewer cannot send invitations."""
        viewer = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=PANTRY_ID, role="viewer"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([viewer]),  # check_resource_permission -> viewer
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "pantry",
                "resource_id": PANTRY_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_shopping_list_not_found(self, client, mock_async_db, mock_user):
        """Shopping list not found returns 404."""
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),  # check_resource_permission -> shopping list not found
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 404

    def test_send_invitation_shopping_list_owner_allowed(self, client, mock_async_db, mock_user):
        """Shopping list owner can send invitation."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Bob", username="bob")
        sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=mock_user.id, is_shared=False
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([sl]),           # check_resource_permission -> found SL, owner matches
            MockExecuteResult([target_user]),   # User lookup by username
            # check_existing_membership: shopping_list path
            MockExecuteResult([]),             # select ShoppingList -> not found (user not owner)
            MockExecuteResult([]),             # select ShoppingListUser -> not a member
            MockExecuteResult([]),             # duplicate invitation check
            MockExecuteResult([0]),            # rate limit count
            MockExecuteResult(["Groceries"]), # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "bob",
            },
        )
        assert response.status_code == 201

    def test_send_invitation_shopping_list_non_owner_no_membership(
        self, client, mock_async_db, mock_user
    ):
        """Non-owner without membership on shopping list gets 403."""
        other_owner_id = str(uuid.uuid4())
        sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=other_owner_id, is_shared=True
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([sl]),   # check_resource_permission -> found SL, not owner
            MockExecuteResult([]),     # ShoppingListUser lookup -> no membership
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_shopping_list_viewer_denied(
        self, client, mock_async_db, mock_user
    ):
        """Viewer on shopping list cannot send invitations."""
        other_owner_id = str(uuid.uuid4())
        sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=other_owner_id, is_shared=True
        )
        viewer = MockShoppingListUser(
            user_id=str(mock_user.id),
            shopping_list_id=SHOPPING_LIST_ID,
            role="viewer",
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([sl]),       # found SL, not owner
            MockExecuteResult([viewer]),   # ShoppingListUser -> viewer role
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_meal_event_not_found(self, client, mock_async_db, mock_user):
        """Meal event not found returns 404."""
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),  # check_resource_permission -> meal event not found
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "someone",
            },
        )
        assert response.status_code == 404

    def test_send_invitation_meal_event_owner_allowed(self, client, mock_async_db, mock_user):
        """Meal event owner can send invitation."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Bob", username="bob")
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=mock_user.id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),            # check_resource_permission -> found, owner matches
            MockExecuteResult([target_user]),    # User lookup by username
            # check_existing_membership: meal_event path
            MockExecuteResult([]),              # select MealEvent -> not found (user not owner)
            MockExecuteResult([]),              # select MealEventParticipant -> not a member
            MockExecuteResult([]),              # duplicate invitation check
            MockExecuteResult([0]),             # rate limit count
            MockExecuteResult(["Dinner"]),      # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "bob",
            },
        )
        assert response.status_code == 201

    def test_send_invitation_meal_event_non_owner_guest_denied(
        self, client, mock_async_db, mock_user
    ):
        """Guest on meal event cannot send invitations (only host/cohost can)."""
        other_owner_id = str(uuid.uuid4())
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=other_owner_id)
        guest = MockMealEventParticipant(
            user_id=str(mock_user.id),
            meal_event_id=MEAL_EVENT_ID,
            role="guest",
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),      # found meal event, not owner
            MockExecuteResult([guest]),   # MealEventParticipant -> guest role
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "someone",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_meal_event_non_owner_no_participant(
        self, client, mock_async_db, mock_user
    ):
        """Non-owner with no participant record on meal event gets 403."""
        other_owner_id = str(uuid.uuid4())
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=other_owner_id)

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),   # found meal event, not owner
            MockExecuteResult([]),     # no participant record
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "cohost",
                "to_username": "someone",
            },
        )
        assert response.status_code == 403

    def test_send_invitation_to_user_id_not_found(self, client, mock_async_db, mock_user):
        """to_user_id that doesn't match any user returns 404."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),  # check_resource_permission
            MockExecuteResult([]),            # User lookup by id -> not found
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_user_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 404

    def test_send_invitation_to_email_existing_user(self, client, mock_async_db, mock_user):
        """to_email that matches an existing user resolves to that user."""
        target_user = MockUser(
            id=str(uuid.uuid4()), name="EmailUser", email="emailuser@example.com"
        )
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),    # check_resource_permission
            MockExecuteResult([target_user]),   # User lookup by email
            MockExecuteResult([]),              # check_existing_membership
            MockExecuteResult([]),              # duplicate invitation check
            MockExecuteResult([0]),             # rate limit count
            MockExecuteResult(["My Book"]),     # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "viewer",
                "to_email": "emailuser@example.com",
            },
        )
        assert response.status_code == 201

    def test_send_invitation_to_email_no_user(self, client, mock_async_db, mock_user):
        """to_email with no matching user creates email-only invitation."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),  # check_resource_permission
            MockExecuteResult([]),            # User lookup by email -> no user
            MockExecuteResult([]),            # duplicate invitation check (email branch)
            MockExecuteResult([0]),           # rate limit count
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "viewer",
                "to_email": "newperson@example.com",
            },
        )
        assert response.status_code == 201

    def test_send_invitation_already_member(self, client, mock_async_db, mock_user):
        """Inviting someone who is already a member returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Member", username="member")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        existing_membership = MockRecipeBookUser(
            user_id=target_user.id, recipe_book_id=BOOK_ID, role="editor"
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),           # check_resource_permission
            MockExecuteResult([target_user]),           # User lookup by username
            MockExecuteResult([existing_membership]),   # check_existing_membership -> already member
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "member",
            },
        )
        assert response.status_code == 409

    def test_send_invitation_duplicate_pending(self, client, mock_async_db, mock_user):
        """Sending a duplicate pending invitation returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Dup", username="dup")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        existing_inv = MockInvitation(status="pending")

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),     # check_resource_permission
            MockExecuteResult([target_user]),     # User lookup by username
            MockExecuteResult([]),                # check_existing_membership -> not member
            MockExecuteResult([existing_inv]),    # duplicate invitation check -> found
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "dup",
            },
        )
        assert response.status_code == 409

    def test_send_invitation_rate_limited(self, client, mock_async_db, mock_user):
        """Exceeding daily limit returns 429."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Ratelimited", username="rl")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),    # check_resource_permission
            MockExecuteResult([target_user]),    # User lookup by username
            MockExecuteResult([]),               # check_existing_membership
            MockExecuteResult([]),               # duplicate invitation check
            MockExecuteResult([30]),             # rate limit count -> at max
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "rl",
            },
        )
        assert response.status_code == 429

    def test_send_invitation_username_not_found(self, client, mock_async_db, mock_user):
        """to_username not matching any user returns 404."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),  # check_resource_permission
            MockExecuteResult([]),            # User lookup by username -> not found
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "nonexistent",
            },
        )
        assert response.status_code == 404

    def test_send_invitation_pantry_editor_allowed(self, client, mock_async_db, mock_user):
        """Pantry editor can send invitations."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Bob", username="bob")
        editor = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=PANTRY_ID, role="editor"
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([editor]),       # check_resource_permission -> editor
            MockExecuteResult([target_user]),   # User lookup
            MockExecuteResult([]),              # check_existing_membership (pantry)
            MockExecuteResult([]),              # duplicate invitation check
            MockExecuteResult([0]),             # rate limit
            MockExecuteResult(["My Pantry"]),   # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "pantry",
                "resource_id": PANTRY_ID,
                "role_offered": "viewer",
                "to_username": "bob",
            },
        )
        assert response.status_code == 201

    def test_send_invitation_shopping_list_editor_allowed(
        self, client, mock_async_db, mock_user
    ):
        """Shopping list editor (non-owner) can send invitations."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Bob", username="bob")
        other_owner_id = str(uuid.uuid4())
        sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=other_owner_id, is_shared=True
        )
        editor = MockShoppingListUser(
            user_id=str(mock_user.id),
            shopping_list_id=SHOPPING_LIST_ID,
            role="editor",
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([sl]),           # check_resource_permission -> found SL, not owner
            MockExecuteResult([editor]),        # ShoppingListUser -> editor
            MockExecuteResult([target_user]),   # User lookup
            # check_existing_membership: shopping_list path
            MockExecuteResult([]),              # ShoppingList lookup (ownership check)
            MockExecuteResult([]),              # ShoppingListUser -> not member
            MockExecuteResult([]),              # duplicate invitation check
            MockExecuteResult([0]),             # rate limit
            MockExecuteResult(["Groceries"]),   # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "bob",
            },
        )
        assert response.status_code == 201

    def test_send_invitation_meal_event_cohost_allowed(
        self, client, mock_async_db, mock_user
    ):
        """Meal event cohost can send invitations."""
        target_user = MockUser(id=str(uuid.uuid4()), name="Bob", username="bob")
        other_owner_id = str(uuid.uuid4())
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=other_owner_id)
        cohost = MockMealEventParticipant(
            user_id=str(mock_user.id),
            meal_event_id=MEAL_EVENT_ID,
            role="cohost",
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),            # check_resource_permission -> found, not owner
            MockExecuteResult([cohost]),         # MealEventParticipant -> cohost
            MockExecuteResult([target_user]),    # User lookup
            # check_existing_membership: meal_event path
            MockExecuteResult([]),               # MealEvent lookup
            MockExecuteResult([]),               # MealEventParticipant -> not participant
            MockExecuteResult([]),               # duplicate invitation check
            MockExecuteResult([0]),              # rate limit
            MockExecuteResult(["Dinner"]),       # get_resource_name
        ]

        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "bob",
            },
        )
        assert response.status_code == 201


# ===================================================================
# TestAcceptInvitation
# ===================================================================


class TestAcceptInvitation:
    """Tests for POST /v1/invitations/{id}/accept."""

    def test_accept_invitation_not_found(self, client, mock_async_db, mock_user):
        """Accepting a nonexistent invitation returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.post("/v1/invitations/nonexistent/accept")
        assert response.status_code in (404, 500)

    def test_accept_invitation_success(self, client, mock_async_db, mock_user):
        """Accepting a valid pending invitation returns 200 with accepted status."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        # Sequence:
        # 1. fetch invitation with joinedload
        # 2. create_membership: check existing RecipeBookUser -> None
        # 3. get_resource_name: RecipeBook.name
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),   # fetch invitation
            MockExecuteResult([]),             # create_membership: check existing
            MockExecuteResult(["My Book"]),    # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["role"] == "editor"

    def test_accept_invitation_wrong_user(self, client, mock_async_db, mock_user):
        """Accepting an invitation addressed to someone else returns 403."""
        invitation_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=other_user_id,  # different from mock_user
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 403

    def test_accept_invitation_already_accepted(self, client, mock_async_db, mock_user):
        """Accepting an already-accepted invitation returns 400."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="accepted",
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 400

    def test_accept_invitation_already_declined(self, client, mock_async_db, mock_user):
        """Accepting an already-declined invitation returns 400."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="declined",
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 400

    def test_accept_invitation_expired(self, client, mock_async_db, mock_user):
        """Accepting an expired invitation returns 410."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 410

    def test_accept_invitation_pantry(self, client, mock_async_db, mock_user):
        """Accepting a pantry invitation creates pantry membership."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="pantry",
            resource_id=PANTRY_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),       # fetch invitation
            MockExecuteResult([]),                 # create_membership: check existing PantryUser
            MockExecuteResult(["My Pantry"]),      # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["resource_type"] == "pantry"

    def test_accept_invitation_shopping_list(self, client, mock_async_db, mock_user):
        """Accepting a shopping list invitation creates membership and marks shared."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        sl = MockShoppingList(id=SHOPPING_LIST_ID, is_shared=False)
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="shopping_list",
            resource_id=SHOPPING_LIST_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),       # fetch invitation
            MockExecuteResult([]),                 # create_membership: check existing ShoppingListUser
            MockExecuteResult([sl]),               # create_membership: select ShoppingList to mark shared
            MockExecuteResult(["Groceries"]),      # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["resource_type"] == "shopping_list"

    def test_accept_invitation_meal_event(self, client, mock_async_db, mock_user):
        """Accepting a meal event invitation creates participant record."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="meal_event",
            resource_id=MEAL_EVENT_ID,
            role_offered="guest",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),        # fetch invitation
            MockExecuteResult([]),                  # create_membership: check existing participant
            MockExecuteResult(["Friday Dinner"]),   # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["resource_type"] == "meal_event"
        assert data["role"] == "guest"

    def test_accept_invitation_reactivates_archived_recipe_book(
        self, client, mock_async_db, mock_user
    ):
        """Accepting re-activates an archived recipe book membership."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        # Existing archived membership
        archived_membership = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="viewer",
            archived_at=datetime.now(UTC) - timedelta(days=10),
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),            # fetch invitation
            MockExecuteResult([archived_membership]),   # create_membership: found archived
            MockExecuteResult(["My Book"]),             # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        # Verify the archived_at was cleared and role updated
        assert archived_membership.archived_at is None
        assert archived_membership.role == "editor"

    def test_accept_invitation_reactivates_archived_pantry(
        self, client, mock_async_db, mock_user
    ):
        """Accepting re-activates an archived pantry membership."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="pantry",
            resource_id=PANTRY_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        archived = MockPantryUser(
            user_id=str(mock_user.id),
            pantry_id=PANTRY_ID,
            role="viewer",
            archived_at=datetime.now(UTC) - timedelta(days=5),
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),  # fetch invitation
            MockExecuteResult([archived]),    # create_membership: found archived
            MockExecuteResult(["Pantry"]),    # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        assert archived.archived_at is None
        assert archived.role == "editor"

    def test_accept_invitation_reactivates_archived_shopping_list(
        self, client, mock_async_db, mock_user
    ):
        """Accepting re-activates an archived shopping list membership."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        sl = MockShoppingList(id=SHOPPING_LIST_ID, is_shared=False)
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="shopping_list",
            resource_id=SHOPPING_LIST_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        archived = MockShoppingListUser(
            user_id=str(mock_user.id),
            shopping_list_id=SHOPPING_LIST_ID,
            role="viewer",
            archived_at=datetime.now(UTC) - timedelta(days=5),
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),    # fetch invitation
            MockExecuteResult([archived]),      # create_membership: found archived
            MockExecuteResult([sl]),            # create_membership: select ShoppingList
            MockExecuteResult(["Groceries"]),   # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        assert archived.archived_at is None
        assert archived.role == "editor"
        assert sl.is_shared is True

    def test_accept_invitation_reactivates_archived_meal_event(
        self, client, mock_async_db, mock_user
    ):
        """Accepting re-activates an archived meal event participant."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="meal_event",
            resource_id=MEAL_EVENT_ID,
            role_offered="cohost",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        archived = MockMealEventParticipant(
            user_id=str(mock_user.id),
            meal_event_id=MEAL_EVENT_ID,
            role="guest",
            status="declined",
            archived_at=datetime.now(UTC) - timedelta(days=5),
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),    # fetch invitation
            MockExecuteResult([archived]),      # create_membership: found archived
            MockExecuteResult(["Dinner"]),      # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200
        assert archived.archived_at is None
        assert archived.role == "cohost"
        assert archived.status == "accepted"

    def test_accept_invitation_idempotent_active_membership(
        self, client, mock_async_db, mock_user
    ):
        """Accepting when already an active member is idempotent."""
        invitation_id = str(uuid.uuid4())
        from_user = MockUser(id=str(uuid.uuid4()), name="Alice")
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
            expires_at=None,
        )
        invitation.from_user = from_user

        # Active (not archived) membership already exists
        active = MockRecipeBookUser(
            user_id=str(mock_user.id),
            recipe_book_id=BOOK_ID,
            role="editor",
            archived_at=None,
        )

        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([invitation]),  # fetch invitation
            MockExecuteResult([active]),      # create_membership: found active -> idempotent
            MockExecuteResult(["My Book"]),   # get_resource_name
        ]

        response = client.post(f"/v1/invitations/{invitation_id}/accept")
        assert response.status_code == 200


# ===================================================================
# TestDeclineInvitation
# ===================================================================


class TestDeclineInvitation:
    """Tests for POST /v1/invitations/{id}/decline."""

    def test_decline_invitation_not_found(self, client, mock_async_db, mock_user):
        """Declining a nonexistent invitation returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.post("/v1/invitations/nonexistent/decline")
        assert response.status_code in (404, 500)

    def test_decline_invitation_success(self, client, mock_async_db, mock_user):
        """Successfully declining a pending invitation returns 200."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/decline")
        assert response.status_code == 200
        assert invitation.status == "declined"
        assert invitation.responded_at is not None

    def test_decline_invitation_wrong_user(self, client, mock_async_db, mock_user):
        """Declining an invitation addressed to someone else returns 403."""
        invitation_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=other_user_id,  # different from mock_user
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/decline")
        assert response.status_code == 403

    def test_decline_invitation_already_accepted(self, client, mock_async_db, mock_user):
        """Declining an already-accepted invitation returns 400."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="accepted",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/decline")
        assert response.status_code == 400

    def test_decline_invitation_already_declined(self, client, mock_async_db, mock_user):
        """Declining an already-declined invitation returns 400."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="declined",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/decline")
        assert response.status_code == 400

    def test_decline_invitation_already_revoked(self, client, mock_async_db, mock_user):
        """Declining an already-revoked invitation returns 400."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="revoked",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.post(f"/v1/invitations/{invitation_id}/decline")
        assert response.status_code == 400


# ===================================================================
# TestRevokeInvitation
# ===================================================================


class TestRevokeInvitation:
    """Tests for DELETE /v1/invitations/{id}."""

    def test_revoke_invitation_not_found(self, client, mock_async_db, mock_user):
        """Revoking a nonexistent invitation returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.delete("/v1/invitations/nonexistent")
        assert response.status_code in (404, 500)

    def test_revoke_success(self, client, mock_async_db, mock_user):
        """Owner can revoke a pending invitation they sent."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=mock_user.id,
            status="pending",
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.delete(f"/v1/invitations/{invitation_id}")
        assert response.status_code == 200
        assert invitation.status == "revoked"

    def test_revoke_invitation_wrong_user(self, client, mock_async_db, mock_user):
        """Revoking an invitation sent by someone else returns 403."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=str(uuid.uuid4()),  # different from mock_user
            status="pending",
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.delete(f"/v1/invitations/{invitation_id}")
        assert response.status_code == 403

    def test_revoke_invitation_already_accepted(self, client, mock_async_db, mock_user):
        """Revoking an already-accepted invitation returns 400."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=mock_user.id,
            status="accepted",
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.delete(f"/v1/invitations/{invitation_id}")
        assert response.status_code == 400

    def test_revoke_invitation_already_declined(self, client, mock_async_db, mock_user):
        """Revoking an already-declined invitation returns 400."""
        invitation_id = str(uuid.uuid4())
        invitation = MockInvitation(
            id=invitation_id,
            from_user_id=mock_user.id,
            status="declined",
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([invitation])

        response = client.delete(f"/v1/invitations/{invitation_id}")
        assert response.status_code == 400


# ===================================================================
# TestClaimInvitations
# ===================================================================


class TestClaimInvitations:
    """Tests for POST /v1/invitations/claim."""

    def test_claim_no_email(self, client, mock_async_db, mock_user):
        """User with no email returns empty list."""
        mock_user.email = None

        response = client.post("/v1/invitations/claim")
        assert response.status_code == 200
        assert response.json() == []

    def test_claim_no_matching_invitations(self, client, mock_async_db, mock_user):
        """No matching pending invitations returns empty list."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post("/v1/invitations/claim")
        assert response.status_code == 200
        assert response.json() == []

    def test_claim_invitations_success(self, client, mock_async_db, mock_user):
        """Claim matches email-based invitations and sets to_user_id."""
        inv1 = MockInvitation(
            to_email=mock_user.email,
            to_user_id=None,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
        )
        inv2 = MockInvitation(
            to_email=mock_user.email,
            to_user_id=None,
            resource_type="pantry",
            resource_id=PANTRY_ID,
            role_offered="viewer",
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([inv1, inv2])

        response = client.post("/v1/invitations/claim")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["resource_type"] == "recipe_book"
        assert data[1]["resource_type"] == "pantry"
        # Verify to_user_id was set
        assert inv1.to_user_id == mock_user.id
        assert inv2.to_user_id == mock_user.id
        # Verify commit was called
        mock_async_db.db.commit.assert_called()

    def test_claim_invitations_empty_no_commit(self, client, mock_async_db, mock_user):
        """When no invitations match, commit is not called."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post("/v1/invitations/claim")
        assert response.status_code == 200
        # commit should NOT have been called since claimed is empty
        # (the if claimed: guard prevents it)


# ===================================================================
# TestHelpers (direct unit tests for helpers.py functions)
# ===================================================================


class TestValidateResourceAndRole:
    """Tests for validate_resource_and_role helper."""

    def test_valid_recipe_book_editor(self, client, mock_async_db, mock_user):
        """recipe_book + editor is valid (no error on valid send)."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Book"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "t",
            },
        )
        assert response.status_code == 201

    def test_valid_recipe_book_viewer(self, client, mock_async_db, mock_user):
        """recipe_book + viewer is valid."""
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Book"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "viewer",
                "to_username": "t",
            },
        )
        assert response.status_code == 201

    def test_invalid_resource_type(self, client, mock_async_db, mock_user):
        """Unknown resource_type returns 400."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "fridge",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 400

    def test_invalid_role_for_pantry(self, client, mock_async_db, mock_user):
        """pantry + guest is invalid (only editor/viewer allowed)."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "pantry",
                "resource_id": PANTRY_ID,
                "role_offered": "guest",
                "to_username": "someone",
            },
        )
        assert response.status_code == 400

    def test_invalid_role_for_shopping_list(self, client, mock_async_db, mock_user):
        """shopping_list + cohost is invalid."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "cohost",
                "to_username": "someone",
            },
        )
        assert response.status_code == 400

    def test_valid_meal_event_cohost(self, client, mock_async_db, mock_user):
        """meal_event + cohost is valid."""
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=mock_user.id)
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Dinner"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "cohost",
                "to_username": "t",
            },
        )
        assert response.status_code == 201

    def test_valid_meal_event_guest(self, client, mock_async_db, mock_user):
        """meal_event + guest is valid."""
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=mock_user.id)
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Dinner"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "t",
            },
        )
        assert response.status_code == 201

    def test_invalid_role_for_meal_event(self, client, mock_async_db, mock_user):
        """meal_event + editor is invalid (only cohost/guest allowed)."""
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "editor",
                "to_username": "someone",
            },
        )
        assert response.status_code == 400


class TestCheckExistingMembership:
    """Tests for check_existing_membership helper via the send endpoint.

    We exercise all branches by sending invitations where the target
    user is already a member of each resource type.
    """

    def test_existing_membership_recipe_book(self, client, mock_async_db, mock_user):
        """Target already a recipe_book member returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        membership = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="owner"
        )
        target_membership = MockRecipeBookUser(
            user_id=target_user.id, recipe_book_id=BOOK_ID, role="editor"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([membership]),          # check_resource_permission
            MockExecuteResult([target_user]),          # User lookup
            MockExecuteResult([target_membership]),    # check_existing_membership -> is member
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "editor",
                "to_username": "t",
            },
        )
        assert response.status_code == 409

    def test_existing_membership_pantry(self, client, mock_async_db, mock_user):
        """Target already a pantry member returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        owner = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=PANTRY_ID, role="owner"
        )
        target_membership = MockPantryUser(
            user_id=target_user.id, pantry_id=PANTRY_ID, role="editor"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([owner]),                # check_resource_permission
            MockExecuteResult([target_user]),           # User lookup
            MockExecuteResult([target_membership]),     # check_existing_membership -> is member
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "pantry",
                "resource_id": PANTRY_ID,
                "role_offered": "viewer",
                "to_username": "t",
            },
        )
        assert response.status_code == 409

    def test_existing_membership_shopping_list_owner(self, client, mock_async_db, mock_user):
        """Target is the shopping list owner returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=mock_user.id
        )
        target_sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=target_user.id
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([sl]),            # check_resource_permission -> owner
            MockExecuteResult([target_user]),    # User lookup
            MockExecuteResult([target_sl]),      # check_existing_membership: ShoppingList -> owner match
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "t",
            },
        )
        assert response.status_code == 409

    def test_existing_membership_shopping_list_member(self, client, mock_async_db, mock_user):
        """Target is an existing shopping list member returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=mock_user.id
        )
        other_sl = MockShoppingList(
            id=SHOPPING_LIST_ID, owner_id=str(uuid.uuid4())
        )
        target_member = MockShoppingListUser(
            user_id=target_user.id,
            shopping_list_id=SHOPPING_LIST_ID,
            role="editor",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([sl]),              # check_resource_permission -> owner
            MockExecuteResult([target_user]),      # User lookup
            MockExecuteResult([other_sl]),         # check_existing_membership: ShoppingList -> not owner
            MockExecuteResult([target_member]),    # ShoppingListUser -> is member
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "t",
            },
        )
        assert response.status_code == 409

    def test_existing_membership_meal_event_owner(self, client, mock_async_db, mock_user):
        """Target is the meal event owner returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=mock_user.id)
        target_me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=target_user.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),             # check_resource_permission -> owner
            MockExecuteResult([target_user]),     # User lookup
            MockExecuteResult([target_me]),       # check_existing_membership: MealEvent -> owner match
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "t",
            },
        )
        assert response.status_code == 409

    def test_existing_membership_meal_event_participant(
        self, client, mock_async_db, mock_user
    ):
        """Target is an existing meal event participant returns 409."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=mock_user.id)
        other_me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=str(uuid.uuid4()))
        target_participant = MockMealEventParticipant(
            user_id=target_user.id,
            meal_event_id=MEAL_EVENT_ID,
            role="guest",
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),                   # check_resource_permission -> owner
            MockExecuteResult([target_user]),            # User lookup
            MockExecuteResult([other_me]),               # check_existing_membership: MealEvent -> not owner
            MockExecuteResult([target_participant]),     # MealEventParticipant -> is participant
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "cohost",
                "to_username": "t",
            },
        )
        assert response.status_code == 409

    def test_no_membership_shopping_list_not_found(self, client, mock_async_db, mock_user):
        """check_existing_membership for shopping list when SL not found -> not member."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        sl = MockShoppingList(id=SHOPPING_LIST_ID, owner_id=mock_user.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([sl]),            # check_resource_permission -> owner
            MockExecuteResult([target_user]),    # User lookup
            MockExecuteResult([]),               # check_existing_membership: ShoppingList -> not found
            MockExecuteResult([]),               # ShoppingListUser -> not member
            MockExecuteResult([]),               # duplicate check
            MockExecuteResult([0]),              # rate limit
            MockExecuteResult(["Groceries"]),    # get_resource_name
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "shopping_list",
                "resource_id": SHOPPING_LIST_ID,
                "role_offered": "editor",
                "to_username": "t",
            },
        )
        assert response.status_code == 201

    def test_no_membership_meal_event_not_found(self, client, mock_async_db, mock_user):
        """check_existing_membership for meal event when ME not found -> not member."""
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=mock_user.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),             # check_resource_permission -> owner
            MockExecuteResult([target_user]),     # User lookup
            MockExecuteResult([]),                # check_existing_membership: MealEvent -> not found
            MockExecuteResult([]),                # MealEventParticipant -> not member
            MockExecuteResult([]),                # duplicate check
            MockExecuteResult([0]),               # rate limit
            MockExecuteResult(["Dinner"]),        # get_resource_name
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "t",
            },
        )
        assert response.status_code == 201


class TestGetResourceName:
    """Tests for get_resource_name helper via the list_sent endpoint."""

    def test_recipe_book_name(self, client, mock_async_db, mock_user):
        """get_resource_name returns recipe book name."""
        inv = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="recipe_book",
            resource_id=BOOK_ID,
            role_offered="editor",
            status="pending",
        )
        inv.to_user = None
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            MockExecuteResult(["Italian Recipes"]),
        ]
        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] == "Italian Recipes"

    def test_pantry_name(self, client, mock_async_db, mock_user):
        """get_resource_name returns pantry name."""
        inv = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="pantry",
            resource_id=PANTRY_ID,
            role_offered="editor",
            status="pending",
        )
        inv.to_user = None
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            MockExecuteResult(["Kitchen Pantry"]),
        ]
        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] == "Kitchen Pantry"

    def test_pantry_not_found(self, client, mock_async_db, mock_user):
        """get_resource_name returns None when pantry doesn't exist."""
        inv = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="pantry",
            resource_id=PANTRY_ID,
            role_offered="editor",
            status="pending",
        )
        inv.to_user = None
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            MockExecuteResult([]),  # pantry not found
        ]
        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] is None

    def test_meal_event_not_found(self, client, mock_async_db, mock_user):
        """get_resource_name returns None when meal event doesn't exist."""
        inv = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="meal_event",
            resource_id=MEAL_EVENT_ID,
            role_offered="guest",
            status="pending",
        )
        inv.to_user = None
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            MockExecuteResult([]),  # meal event not found
        ]
        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] is None

    def test_shopping_list_name_none_fallback(self, client, mock_async_db, mock_user):
        """get_resource_name for shopping_list with None name returns 'Shopping List'."""
        inv = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="shopping_list",
            resource_id=SHOPPING_LIST_ID,
            role_offered="editor",
            status="pending",
        )
        inv.to_user = None
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            MockExecuteResult([None]),  # shopping list name is None
        ]
        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] == "Shopping List"

    def test_unknown_resource_type_returns_none(self, client, mock_async_db, mock_user):
        """get_resource_name for an unknown resource_type returns None."""
        inv = MockInvitation(
            from_user_id=mock_user.id,
            resource_type="galaxy",
            resource_id=str(uuid.uuid4()),
            role_offered="editor",
            status="pending",
        )
        inv.to_user = None
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            # No DB call for unknown type
        ]
        response = client.get("/v1/invitations/sent")
        assert response.status_code == 200
        assert response.json()[0]["resource_name"] is None


class TestCheckResourcePermission:
    """Tests for check_resource_permission helper via the send endpoint."""

    def test_recipe_book_editor_allowed(self, client, mock_async_db, mock_user):
        """Recipe book editor has permission to invite."""
        editor = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="editor"
        )
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([editor]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Book"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "viewer",
                "to_username": "t",
            },
        )
        assert response.status_code == 201

    def test_recipe_book_viewer_denied(self, client, mock_async_db, mock_user):
        """Recipe book viewer cannot invite."""
        viewer = MockRecipeBookUser(
            user_id=str(mock_user.id), recipe_book_id=BOOK_ID, role="viewer"
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([viewer])
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "viewer",
                "to_username": "t",
            },
        )
        assert response.status_code == 403

    def test_recipe_book_no_membership(self, client, mock_async_db, mock_user):
        """No membership on recipe book returns 403."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "recipe_book",
                "resource_id": BOOK_ID,
                "role_offered": "viewer",
                "to_username": "t",
            },
        )
        assert response.status_code == 403

    def test_pantry_owner_allowed(self, client, mock_async_db, mock_user):
        """Pantry owner has permission to invite."""
        owner = MockPantryUser(
            user_id=str(mock_user.id), pantry_id=PANTRY_ID, role="owner"
        )
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([owner]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Pantry"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "pantry",
                "resource_id": PANTRY_ID,
                "role_offered": "editor",
                "to_username": "t",
            },
        )
        assert response.status_code == 201

    def test_pantry_no_membership(self, client, mock_async_db, mock_user):
        """No membership on pantry returns 403."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "pantry",
                "resource_id": PANTRY_ID,
                "role_offered": "editor",
                "to_username": "t",
            },
        )
        assert response.status_code == 403

    def test_meal_event_host_participant_allowed(self, client, mock_async_db, mock_user):
        """Meal event host participant can invite."""
        other_owner = str(uuid.uuid4())
        me = MockMealEvent(id=MEAL_EVENT_ID, owner_id=other_owner)
        host = MockMealEventParticipant(
            user_id=str(mock_user.id), meal_event_id=MEAL_EVENT_ID, role="host"
        )
        target_user = MockUser(id=str(uuid.uuid4()), username="t")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([me]),
            MockExecuteResult([host]),
            MockExecuteResult([target_user]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
            MockExecuteResult(["Dinner"]),
        ]
        response = client.post(
            "/v1/invitations",
            json={
                "resource_type": "meal_event",
                "resource_id": MEAL_EVENT_ID,
                "role_offered": "guest",
                "to_username": "t",
            },
        )
        assert response.status_code == 201


class TestCreateMembership:
    """Tests for create_membership helper via the accept endpoint.

    Covers new creation, archived reactivation, and idempotent active
    paths for each resource type.
    """

    def _make_invitation(self, mock_user, resource_type, resource_id, role):
        """Helper to create a standard pending invitation for accept tests."""
        from_user = MockUser(id=str(uuid.uuid4()), name="Inviter")
        inv = MockInvitation(
            id=str(uuid.uuid4()),
            from_user_id=from_user.id,
            to_user_id=mock_user.id,
            resource_type=resource_type,
            resource_id=resource_id,
            role_offered=role,
            status="pending",
            expires_at=None,
        )
        inv.from_user = from_user
        return inv

    def test_create_new_pantry_membership(self, client, mock_async_db, mock_user):
        """Accept creates new PantryUser when none exists."""
        inv = self._make_invitation(mock_user, "pantry", PANTRY_ID, "editor")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),          # fetch invitation
            MockExecuteResult([]),             # create_membership: no existing PantryUser
            MockExecuteResult(["Pantry"]),     # get_resource_name
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200
        # db.add was called to create the new membership
        assert mock_async_db.db.add.called

    def test_create_new_shopping_list_membership(self, client, mock_async_db, mock_user):
        """Accept creates new ShoppingListUser and marks list as shared."""
        sl = MockShoppingList(id=SHOPPING_LIST_ID, is_shared=False)
        inv = self._make_invitation(
            mock_user, "shopping_list", SHOPPING_LIST_ID, "editor"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),       # fetch invitation
            MockExecuteResult([]),          # create_membership: no existing
            MockExecuteResult([sl]),        # create_membership: select ShoppingList
            MockExecuteResult(["List"]),    # get_resource_name
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200
        assert sl.is_shared is True

    def test_create_shopping_list_already_shared(self, client, mock_async_db, mock_user):
        """Accepting on an already-shared shopping list stays shared."""
        sl = MockShoppingList(id=SHOPPING_LIST_ID, is_shared=True)
        inv = self._make_invitation(
            mock_user, "shopping_list", SHOPPING_LIST_ID, "editor"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            MockExecuteResult([]),
            MockExecuteResult([sl]),
            MockExecuteResult(["List"]),
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200
        assert sl.is_shared is True

    def test_create_new_meal_event_participant(self, client, mock_async_db, mock_user):
        """Accept creates new MealEventParticipant with status=accepted."""
        inv = self._make_invitation(mock_user, "meal_event", MEAL_EVENT_ID, "guest")
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),
            MockExecuteResult([]),
            MockExecuteResult(["Dinner"]),
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200
        assert mock_async_db.db.add.called

    def test_idempotent_active_pantry_membership(self, client, mock_async_db, mock_user):
        """Accepting with an existing active pantry membership is idempotent."""
        inv = self._make_invitation(mock_user, "pantry", PANTRY_ID, "editor")
        active = MockPantryUser(
            user_id=str(mock_user.id),
            pantry_id=PANTRY_ID,
            role="editor",
            archived_at=None,
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),       # fetch invitation
            MockExecuteResult([active]),    # create_membership: found active -> idempotent
            MockExecuteResult(["Pantry"]),  # get_resource_name
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200

    def test_idempotent_active_shopping_list_membership(
        self, client, mock_async_db, mock_user
    ):
        """Accepting with an existing active shopping list membership is idempotent."""
        sl = MockShoppingList(id=SHOPPING_LIST_ID, is_shared=True)
        inv = self._make_invitation(
            mock_user, "shopping_list", SHOPPING_LIST_ID, "editor"
        )
        active = MockShoppingListUser(
            user_id=str(mock_user.id),
            shopping_list_id=SHOPPING_LIST_ID,
            role="editor",
            archived_at=None,
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),        # fetch invitation
            MockExecuteResult([active]),     # create_membership: found active -> idempotent
            MockExecuteResult([sl]),         # create_membership: select ShoppingList
            MockExecuteResult(["List"]),     # get_resource_name
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200

    def test_idempotent_active_meal_event_participant(
        self, client, mock_async_db, mock_user
    ):
        """Accepting with an existing active meal event participant is idempotent."""
        inv = self._make_invitation(mock_user, "meal_event", MEAL_EVENT_ID, "guest")
        active = MockMealEventParticipant(
            user_id=str(mock_user.id),
            meal_event_id=MEAL_EVENT_ID,
            role="guest",
            status="accepted",
            archived_at=None,
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),        # fetch invitation
            MockExecuteResult([active]),     # create_membership: found active -> idempotent
            MockExecuteResult(["Dinner"]),   # get_resource_name
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200

    def test_create_shopping_list_not_found_for_shared_flag(
        self, client, mock_async_db, mock_user
    ):
        """create_membership for shopping_list when SL not found skips shared flag."""
        inv = self._make_invitation(
            mock_user, "shopping_list", SHOPPING_LIST_ID, "editor"
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([inv]),     # fetch invitation
            MockExecuteResult([]),        # create_membership: no existing
            MockExecuteResult([]),        # create_membership: ShoppingList not found
            MockExecuteResult(["List"]),  # get_resource_name
        ]
        response = client.post(f"/v1/invitations/{inv.id}/accept")
        assert response.status_code == 200
