"""Tests for user endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from conftest import MockExecuteResult, MockFriendRequest, MockRecipeBookUser, MockShoppingList, MockUser


class TestGetMe:
    """Tests for GET /v1/users/me."""

    def test_get_me_success(self, client, mock_user, mock_db):
        """Test getting current user profile."""
        mock_db.db.execute.return_value = MockExecuteResult([0])
        response = client.get("/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(mock_user.id)
        assert data["email"] == mock_user.email
        assert data["name"] == mock_user.name

    def test_get_me_returns_username(self, client, mock_user, mock_db):
        """Test that username is included in response."""
        mock_db.db.execute.return_value = MockExecuteResult([0])
        response = client.get("/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == mock_user.username


class TestCheckUsername:
    """Tests for GET /v1/users/check-username/{username}."""

    def test_valid_available_username(self, client, mock_db):
        """Test checking an available username."""
        mock_db.db.execute.return_value = MockExecuteResult([None])
        response = client.get("/v1/users/check-username/newuser")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["username"] == "newuser"

    def test_reserved_username(self, client, mock_db):
        """Test checking a reserved username."""
        response = client.get("/v1/users/check-username/admin")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["reason"] == "reserved"

    def test_invalid_format_username(self, client, mock_db):
        """Test checking a username with invalid format."""
        response = client.get("/v1/users/check-username/AB")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["reason"] == "invalid_format"

    def test_taken_username(self, client, mock_db):
        """Test checking a taken username."""
        existing = MockUser(username="taken")
        mock_db.db.execute.return_value = MockExecuteResult([existing])
        response = client.get("/v1/users/check-username/taken")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["reason"] == "taken"

    def test_username_with_at_prefix(self, client, mock_db):
        """Test that @ prefix is stripped."""
        mock_db.db.execute.return_value = MockExecuteResult([None])
        response = client.get("/v1/users/check-username/@validname")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "validname"


class TestSetUsername:
    """Tests for PUT /v1/users/me/username."""

    def test_set_username_success(self, client, mock_user, mock_db):
        """Test setting a username for the first time."""
        mock_user.username = None
        mock_user.username_changed_at = None
        mock_db.db.execute.return_value = MockExecuteResult([None])
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me/username",
            json={"username": "newuser"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["username"] == "newuser"

    def test_set_username_reserved(self, client, mock_user, mock_db):
        """Test setting a reserved username fails."""
        mock_user.username = None
        response = client.put(
            "/v1/users/me/username",
            json={"username": "admin"}
        )
        assert response.status_code == 400

    def test_set_username_too_short(self, client, mock_user, mock_db):
        """Test setting a username that's too short fails validation."""
        response = client.put(
            "/v1/users/me/username",
            json={"username": "ab"}
        )
        assert response.status_code == 422

    def test_set_username_too_long(self, client, mock_user, mock_db):
        """Test setting a username that's too long fails validation."""
        response = client.put(
            "/v1/users/me/username",
            json={"username": "a" * 21}
        )
        assert response.status_code == 422

    def test_set_username_invalid_format(self, client, mock_user, mock_db):
        """Test setting a username with invalid format (starts with number)."""
        mock_user.username = None
        response = client.put(
            "/v1/users/me/username",
            json={"username": "1invalid"}
        )
        assert response.status_code == 400

    def test_set_username_invalid_chars(self, client, mock_user, mock_db):
        """Test setting a username with special characters fails."""
        mock_user.username = None
        response = client.put(
            "/v1/users/me/username",
            json={"username": "user-name"}
        )
        assert response.status_code == 400

    def test_set_username_already_taken(self, client, mock_user, mock_db):
        """Test setting a username that's already taken fails."""
        mock_user.username = None
        mock_user.username_changed_at = None
        existing = MockUser(username="taken")
        mock_db.db.execute.return_value = MockExecuteResult([existing])

        response = client.put(
            "/v1/users/me/username",
            json={"username": "taken"}
        )
        assert response.status_code == 400

    def test_set_username_cooldown_active(self, client, mock_user, mock_db):
        """Test that username change is blocked during cooldown period."""
        mock_user.username = "oldname"
        mock_user.username_changed_at = datetime.now(UTC) - timedelta(days=5)

        response = client.put(
            "/v1/users/me/username",
            json={"username": "newname"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "days" in data["error_message"]

    def test_set_username_cooldown_expired(self, client, mock_user, mock_db):
        """Test that username change is allowed after cooldown expires."""
        mock_user.username = "oldname"
        mock_user.username_changed_at = datetime.now(UTC) - timedelta(days=31)
        mock_db.db.execute.return_value = MockExecuteResult([None])
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me/username",
            json={"username": "newname"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["username"] == "newname"
        assert data["message"] == "Username updated successfully"

    def test_set_username_first_time_message(self, client, mock_user, mock_db):
        """Test that initial set returns 'set' message, not 'updated'."""
        mock_user.username = None
        mock_user.username_changed_at = None
        mock_db.db.execute.return_value = MockExecuteResult([None])
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me/username",
            json={"username": "firstuser"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Username set successfully"

    def test_set_username_update_sets_changed_at(self, client, mock_user, mock_db):
        """Test that updating an existing username sets username_changed_at."""
        mock_user.username = "oldname"
        mock_user.username_changed_at = datetime.now(UTC) - timedelta(days=31)
        mock_db.db.execute.return_value = MockExecuteResult([None])
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me/username",
            json={"username": "newname"}
        )
        assert response.status_code == 200
        # username_changed_at should have been updated
        assert mock_user.username_changed_at is not None
        # Should be recent (within last few seconds)
        assert (datetime.now(UTC) - mock_user.username_changed_at).total_seconds() < 5

    def test_set_username_first_time_no_changed_at(self, client, mock_user, mock_db):
        """Test that first-time set does NOT update username_changed_at."""
        mock_user.username = None
        mock_user.username_changed_at = None
        mock_db.db.execute.return_value = MockExecuteResult([None])
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me/username",
            json={"username": "brandnew"}
        )
        assert response.status_code == 200
        # Since old_username was None, username_changed_at should not have been set
        assert mock_user.username_changed_at is None

    def test_set_username_has_username_but_no_changed_at(self, client, mock_user, mock_db):
        """Test cooldown check when user has username but no changed_at (legacy users)."""
        mock_user.username = "legacy"
        mock_user.username_changed_at = None  # legacy: no timestamp
        mock_db.db.execute.return_value = MockExecuteResult([None])
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        # Should succeed because the cooldown check requires BOTH username AND username_changed_at
        response = client.put(
            "/v1/users/me/username",
            json={"username": "newlegacy"}
        )
        assert response.status_code == 200


class TestUpdateMe:
    """Tests for PUT /v1/users/me."""

    def test_update_name_success(self, client, mock_user, mock_db):
        """Test updating user name."""
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me",
            json={"name": "New Name"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Profile updated successfully"
        assert mock_user.name == "New Name"

    def test_update_with_null_name(self, client, mock_user, mock_db):
        """Test that sending null name doesn't change existing name."""
        original_name = mock_user.name
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me",
            json={"name": None}
        )
        assert response.status_code == 200
        assert mock_user.name == original_name

    def test_update_with_empty_body(self, client, mock_user, mock_db):
        """Test that empty body still returns success."""
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()

        response = client.put(
            "/v1/users/me",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_with_whitespace_only_name(self, client, mock_user, mock_db):
        """Test that whitespace-only name is rejected."""
        response = client.put(
            "/v1/users/me",
            json={"name": "   "}
        )
        assert response.status_code == 400

    def test_update_with_empty_string_name(self, client, mock_user, mock_db):
        """Test that empty string name is rejected."""
        response = client.put(
            "/v1/users/me",
            json={"name": ""}
        )
        assert response.status_code == 400

    def test_update_with_too_long_name(self, client, mock_user, mock_db):
        """Test that name over 100 characters is rejected."""
        response = client.put(
            "/v1/users/me",
            json={"name": "A" * 101}
        )
        assert response.status_code == 422


class TestSearchUsers:
    """Tests for GET /v1/users/search."""

    def test_search_users_success(self, client, mock_db):
        """Test searching for users."""
        other_user = MockUser(
            username="otheruser",
            name="Other User",
            picture=None,
        )
        mock_db.db.execute.return_value = MockExecuteResult([])

        # First call returns search results, subsequent calls return friendship data
        results = [other_user]
        call_count = [0]
        original_execute = mock_db.db.execute

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                result = MockExecuteResult(results)
                result.scalars = lambda: MockExecuteResult(results)
                return result
            result = MockExecuteResult([])
            result.scalars = lambda: MockExecuteResult([])
            return result

        mock_db.db.execute.side_effect = side_effect
        response = client.get("/v1/users/search?q=other")
        assert response.status_code == 200

    def test_search_users_empty_query(self, client, mock_db):
        """Test searching with empty query fails."""
        response = client.get("/v1/users/search?q=")
        assert response.status_code == 422

    def test_search_users_at_prefix(self, client, mock_db):
        """Test searching with @ prefix strips it correctly."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MockExecuteResult([])
            result.scalars = lambda: MockExecuteResult([])
            return result

        mock_db.db.execute.side_effect = side_effect
        response = client.get("/v1/users/search?q=@john")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_search_users_with_friends(self, client, mock_db, mock_user):
        """Test search returns friendship status correctly."""
        friend = MockUser(username="myfriend", name="My Friend")
        stranger = MockUser(username="stranger", name="A Stranger")
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Search results
                result = MockExecuteResult([friend, stranger])
                result.scalars = lambda: MockExecuteResult([friend, stranger])
                return result
            elif call_count[0] == 2:
                # Friendships
                result = MockExecuteResult([friend.id])
                result.scalars = lambda: MockExecuteResult([friend.id])
                return result
            elif call_count[0] == 3:
                # Sent requests
                result = MockExecuteResult([])
                result.scalars = lambda: MockExecuteResult([])
                return result
            elif call_count[0] == 4:
                # Received requests
                result = MockExecuteResult([])
                result.scalars = lambda: MockExecuteResult([])
                return result
            return MockExecuteResult([])

        mock_db.db.execute.side_effect = side_effect
        response = client.get("/v1/users/search?q=user")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_search_users_with_sent_request(self, client, mock_db, mock_user):
        """Test search shows request_sent status for pending outgoing request."""
        target = MockUser(username="target", name="Target User")
        friend_req = MockFriendRequest(
            from_user_id=str(mock_user.id),
            to_user_id=str(target.id),
            status="pending",
        )
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                result = MockExecuteResult([target])
                result.scalars = lambda: MockExecuteResult([target])
                return result
            elif call_count[0] == 2:
                # Friendships
                result = MockExecuteResult([])
                result.scalars = lambda: MockExecuteResult([])
                return result
            elif call_count[0] == 3:
                # Sent requests
                result = MockExecuteResult([friend_req])
                result.scalars = lambda: MockExecuteResult([friend_req])
                return result
            elif call_count[0] == 4:
                # Received requests
                result = MockExecuteResult([])
                result.scalars = lambda: MockExecuteResult([])
                return result
            return MockExecuteResult([])

        mock_db.db.execute.side_effect = side_effect
        response = client.get("/v1/users/search?q=target")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["friendship_status"] == "request_sent"
        assert data["results"][0]["friend_request_id"] is not None

    def test_search_users_with_received_request(self, client, mock_db, mock_user):
        """Test search shows request_received status for pending incoming request."""
        sender = MockUser(username="sender", name="Sender User")
        friend_req = MockFriendRequest(
            from_user_id=str(sender.id),
            to_user_id=str(mock_user.id),
            status="pending",
        )
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                result = MockExecuteResult([sender])
                result.scalars = lambda: MockExecuteResult([sender])
                return result
            elif call_count[0] == 2:
                # Friendships
                result = MockExecuteResult([])
                result.scalars = lambda: MockExecuteResult([])
                return result
            elif call_count[0] == 3:
                # Sent requests
                result = MockExecuteResult([])
                result.scalars = lambda: MockExecuteResult([])
                return result
            elif call_count[0] == 4:
                # Received requests
                result = MockExecuteResult([friend_req])
                result.scalars = lambda: MockExecuteResult([friend_req])
                return result
            return MockExecuteResult([])

        mock_db.db.execute.side_effect = side_effect
        response = client.get("/v1/users/search?q=sender")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["friendship_status"] == "request_received"
        assert data["results"][0]["friend_request_id"] is not None

    def test_search_users_empty_query_direct(self, mock_db, mock_user):
        """Test that empty query raises APIException (tests the branch not reachable via router)."""
        from api.v1.user.search_users import SearchUsers
        from utils.api.endpoint import APIException

        endpoint = SearchUsers(user=mock_user, database=mock_db)
        try:
            endpoint.execute(q="   ")
            assert False, "Should have raised APIException"
        except APIException as e:
            assert e.status_code == 400
            assert "required" in e.detail.lower()

    def test_search_users_limit_capped(self, client, mock_db):
        """Test that limit is capped at 50."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MockExecuteResult([])
            result.scalars = lambda: MockExecuteResult([])
            return result

        mock_db.db.execute.side_effect = side_effect
        # Request limit=50 (max allowed by router)
        response = client.get("/v1/users/search?q=test&limit=50")
        assert response.status_code == 200


class TestNotificationPreferences:
    """Tests for notification preference endpoints."""

    def test_get_notification_preferences(self, client, mock_user, mock_db):
        """Test getting notification preferences."""
        response = client.get("/v1/users/me/notification-preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["push_enabled"] is True
        assert "timezone" in data

    def test_get_notification_preferences_no_prefs(self, client, mock_user, mock_db):
        """Test getting notification preferences when user has no prefs set."""
        mock_user.notification_preferences = None
        response = client.get("/v1/users/me/notification-preferences")
        assert response.status_code == 200
        data = response.json()
        # Should return defaults
        assert data["push_enabled"] is True
        assert data["email_digest"] == "daily"
        assert data["quiet_hours_start"] == "22:00"
        assert data["quiet_hours_end"] == "08:00"
        assert data["timezone"] == "America/Denver"
        assert data["partner_activity"] is True
        assert data["token_count"] == 0

    def test_get_notification_preferences_with_tokens(self, client, mock_user, mock_db):
        """Test that token_count reflects push_tokens length."""
        mock_user.push_tokens = ["token1", "token2"]
        response = client.get("/v1/users/me/notification-preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["token_count"] == 2

    def test_update_notification_preferences(self, client, mock_user, mock_db):
        """Test updating notification preferences."""
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()
        response = client.put(
            "/v1/users/me/notification-preferences",
            json={"push_enabled": False}
        )
        assert response.status_code == 200

    def test_update_notification_preferences_all_fields(self, client, mock_user, mock_db):
        """Test updating all notification preference fields."""
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()
        response = client.put(
            "/v1/users/me/notification-preferences",
            json={
                "push_enabled": False,
                "email_digest": "weekly",
                "quiet_hours_start": "23:00",
                "quiet_hours_end": "07:00",
                "timezone": "America/New_York",
                "partner_activity": False,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["push_enabled"] is False
        assert data["email_digest"] == "weekly"
        assert data["quiet_hours_start"] == "23:00"
        assert data["quiet_hours_end"] == "07:00"
        assert data["timezone"] == "America/New_York"
        assert data["partner_activity"] is False

    def test_update_notification_preferences_no_existing_prefs(self, client, mock_user, mock_db):
        """Test updating preferences when user has no existing prefs (uses defaults)."""
        mock_user.notification_preferences = None
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()
        response = client.put(
            "/v1/users/me/notification-preferences",
            json={"push_enabled": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["push_enabled"] is False
        # Other fields should have defaults
        assert data["email_digest"] == "daily"

    def test_update_notification_preferences_empty_body(self, client, mock_user, mock_db):
        """Test updating with empty body returns current preferences."""
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()
        response = client.put(
            "/v1/users/me/notification-preferences",
            json={}
        )
        assert response.status_code == 200

    def test_get_returns_categories_defaulted_to_true(
        self, client, mock_user, mock_db
    ):
        """GET prefs echoes a fully-defaulted categories block (all ON)."""
        mock_user.notification_preferences = {"push_enabled": True}
        response = client.get("/v1/users/me/notification-preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["categories"] == {
            "meals": True,
            "timers": True,
            "shopping": True,
            "partner_activity": True,
            "imports": True,
            "friends_invitations": True,
        }

    def test_get_returns_categories_with_user_opt_outs_preserved(
        self, client, mock_user, mock_db
    ):
        """GET prefs preserves user-set False overrides; missing keys default ON."""
        mock_user.notification_preferences = {
            "push_enabled": True,
            "categories": {"imports": False, "shopping": False},
        }
        response = client.get("/v1/users/me/notification-preferences")
        data = response.json()
        assert data["categories"]["imports"] is False
        assert data["categories"]["shopping"] is False
        assert data["categories"]["meals"] is True  # defaulted
        assert data["categories"]["timers"] is True  # defaulted

    def test_update_notification_preferences_categories_partial(
        self, client, mock_user, mock_db
    ):
        """PUT with categories merges into existing categories (preserves others)."""
        mock_user.notification_preferences = {
            "push_enabled": True,
            "categories": {"imports": False},
        }
        mock_db.db.commit = MagicMock()
        response = client.put(
            "/v1/users/me/notification-preferences",
            json={"categories": {"shopping": False}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["categories"]["imports"] is False  # preserved
        assert data["categories"]["shopping"] is False  # newly set
        assert data["categories"]["meals"] is True  # defaulted

    def test_update_notification_preferences_unknown_category_key_400(
        self, client, mock_user, mock_db
    ):
        """PUT with an unknown category key returns 400 with descriptive error."""
        mock_db.db.commit = MagicMock()
        response = client.put(
            "/v1/users/me/notification-preferences",
            json={"categories": {"imports": False, "not_a_real_category": True}},
        )
        assert response.status_code == 400
        body = response.json()
        # Error message should call out the bad key + list valid options.
        error_message = body.get("error_message") or ""
        assert "not_a_real_category" in error_message
        assert "imports" in error_message  # valid keys included


class TestPushTokens:
    """Tests for push token endpoints."""

    def test_register_push_token(self, client, mock_user, mock_db):
        """Test registering a push token."""
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()
        response = client.post(
            "/v1/users/me/push-tokens",
            json={"token": "test-token-123", "platform": "ios"}
        )
        assert response.status_code == 200

    def test_register_push_token_new_token(self, client, mock_user, mock_db):
        """Test registering a new push token adds it to the list."""
        mock_user.push_tokens = []
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/push-tokens",
            json={"token": "new-token-abc"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is True
        assert data["token_count"] == 1

    def test_register_push_token_duplicate(self, client, mock_user, mock_db):
        """Test registering an already-existing token does not duplicate."""
        mock_user.push_tokens = ["existing-token"]
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/push-tokens",
            json={"token": "existing-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is True
        assert data["token_count"] == 1

    def test_register_push_token_null_tokens(self, client, mock_user, mock_db):
        """Test registering when user.push_tokens is None."""
        mock_user.push_tokens = None
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/push-tokens",
            json={"token": "first-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is True
        assert data["token_count"] == 1

    def test_unregister_push_token(self, client, mock_user, mock_db):
        """Test unregistering a push token."""
        mock_user.push_tokens = [
            {"token": "test-token-123", "platform": "ios"}
        ]
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()
        response = client.request(
            "DELETE",
            "/v1/users/me/push-tokens",
            json={"token": "test-token-123"}
        )
        assert response.status_code == 200

    def test_unregister_push_token_removes(self, client, mock_user, mock_db):
        """Test unregistering a token removes it from the list."""
        mock_user.push_tokens = ["token-a", "token-b"]
        mock_db.db.commit = MagicMock()
        response = client.request(
            "DELETE",
            "/v1/users/me/push-tokens",
            json={"token": "token-a"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unregistered"] is True
        assert data["token_count"] == 1

    def test_unregister_push_token_not_present(self, client, mock_user, mock_db):
        """Test unregistering a token that's not present still succeeds."""
        mock_user.push_tokens = ["other-token"]
        mock_db.db.commit = MagicMock()
        response = client.request(
            "DELETE",
            "/v1/users/me/push-tokens",
            json={"token": "nonexistent-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unregistered"] is True
        assert data["token_count"] == 1

    def test_unregister_push_token_null_tokens(self, client, mock_user, mock_db):
        """Test unregistering when user.push_tokens is None."""
        mock_user.push_tokens = None
        mock_db.db.commit = MagicMock()
        response = client.request(
            "DELETE",
            "/v1/users/me/push-tokens",
            json={"token": "any-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unregistered"] is True
        assert data["token_count"] == 0


class TestCompleteOnboarding:
    """Tests for POST /v1/users/me/complete-onboarding."""

    def test_complete_onboarding_success(self, client, mock_user, mock_db):
        """Test successful onboarding creates recipe book and marks user as onboarded."""
        from datetime import UTC, datetime

        mock_user.has_completed_onboarding = False
        mock_user.username = None
        mock_user.username_changed_at = None
        mock_db.db.commit = MagicMock()
        mock_db.db.flush = MagicMock()
        mock_db.db.add = MagicMock()

        def refresh_with_defaults(obj):
            """Apply defaults that the DB would normally set."""
            if not hasattr(obj, 'id') or obj.id is None:
                obj.id = str(uuid.uuid4())
            if hasattr(obj, 'created_at') and obj.created_at is None:
                obj.created_at = datetime.now(UTC)
            if hasattr(obj, 'updated_at') and obj.updated_at is None:
                obj.updated_at = datetime.now(UTC)

        mock_db.db.refresh = MagicMock(side_effect=refresh_with_defaults)

        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={"name": "Leo", "start_method": "browse"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["start_method"] == "browse"
        assert data["recipe_book"] is not None
        assert data["recipe_book"]["name"] == "My Recipes"
        assert mock_user.name == "Leo"
        assert mock_user.has_completed_onboarding is True

    def test_complete_onboarding_empty_name(self, client, mock_user, mock_db):
        """Test that empty name is rejected."""
        mock_user.has_completed_onboarding = False
        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={"name": "", "start_method": "browse"}
        )
        assert response.status_code == 400

    def test_complete_onboarding_whitespace_name(self, client, mock_user, mock_db):
        """Test that whitespace-only name is rejected."""
        mock_user.has_completed_onboarding = False
        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={"name": "   ", "start_method": "browse"}
        )
        assert response.status_code == 400

    def test_complete_onboarding_too_long_name(self, client, mock_user, mock_db):
        """Test that name over 100 characters is rejected."""
        mock_user.has_completed_onboarding = False
        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={"name": "A" * 101, "start_method": "browse"}
        )
        assert response.status_code == 422

    def test_complete_onboarding_already_onboarded(self, client, mock_user, mock_db):
        """Test that already-onboarded user returns existing data without side effects."""
        mock_user.has_completed_onboarding = True
        mock_user.name = "Existing Name"
        mock_user.default_recipe_book_id = "existing-book-id"
        mock_db.db.add = MagicMock()

        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={"name": "New Name", "start_method": "import"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Name should NOT have changed
        assert mock_user.name == "Existing Name"
        # db.add should NOT have been called (no new recipe book)
        mock_db.db.add.assert_not_called()

    def test_complete_onboarding_default_list_bootstrap_failure_is_swallowed(
        self, client, mock_user, mock_db
    ):
        """Default-list bootstrap failure must NOT fail onboarding.

        The migration backfill sweep is the safety net (bugs-onb-1), so a
        post-commit exception is logged and swallowed. Covers the except
        branch in complete_onboarding.py.
        """
        from datetime import UTC, datetime

        mock_user.has_completed_onboarding = False
        mock_user.username = None
        mock_user.username_changed_at = None
        mock_db.db.commit = MagicMock()
        mock_db.db.flush = MagicMock()
        mock_db.db.add = MagicMock()

        def refresh_with_defaults(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = str(uuid.uuid4())
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(UTC)
            if hasattr(obj, "updated_at") and obj.updated_at is None:
                obj.updated_at = datetime.now(UTC)

        mock_db.db.refresh = MagicMock(side_effect=refresh_with_defaults)

        with patch(
            "api.v1.user.complete_onboarding.ensure_default_shopping_list",
            side_effect=RuntimeError("simulated bootstrap failure"),
        ):
            response = client.post(
                "/v1/users/me/complete-onboarding",
                json={"name": "Leo", "start_method": "browse"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert mock_user.has_completed_onboarding is True

    def test_notification_permission_status_persisted_when_granted(
        self, client, mock_user, mock_db
    ):
        """notif-4: the OS AuthorizationStatus outcome must be persisted."""
        from datetime import UTC, datetime

        mock_user.has_completed_onboarding = False
        mock_user.notification_permission_status = None
        mock_db.db.refresh = MagicMock(
            side_effect=lambda obj: (
                setattr(obj, "id", getattr(obj, "id", None) or str(uuid.uuid4())),
                setattr(obj, "created_at", getattr(obj, "created_at", None) or datetime.now(UTC)),
                setattr(obj, "updated_at", getattr(obj, "updated_at", None) or datetime.now(UTC)),
            )
        )

        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={
                "name": "Leo",
                "start_method": "browse",
                "notification_permission_status": "granted",
            },
        )

        assert response.status_code == 200
        assert mock_user.notification_permission_status == "granted"

    def test_notification_permission_status_persisted_when_declined(
        self, client, mock_user, mock_db
    ):
        from datetime import UTC, datetime

        mock_user.has_completed_onboarding = False
        mock_user.notification_permission_status = None
        mock_db.db.refresh = MagicMock(
            side_effect=lambda obj: (
                setattr(obj, "id", getattr(obj, "id", None) or str(uuid.uuid4())),
                setattr(obj, "created_at", getattr(obj, "created_at", None) or datetime.now(UTC)),
                setattr(obj, "updated_at", getattr(obj, "updated_at", None) or datetime.now(UTC)),
            )
        )

        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={
                "name": "Leo",
                "start_method": "scratch",
                "notification_permission_status": "declined",
            },
        )

        assert response.status_code == 200
        assert mock_user.notification_permission_status == "declined"

    def test_notification_permission_status_missing_is_optional(
        self, client, mock_user, mock_db
    ):
        """Older clients don't send the field — onboarding must still succeed."""
        from datetime import UTC, datetime

        mock_user.has_completed_onboarding = False
        mock_user.notification_permission_status = None
        mock_db.db.refresh = MagicMock(
            side_effect=lambda obj: (
                setattr(obj, "id", getattr(obj, "id", None) or str(uuid.uuid4())),
                setattr(obj, "created_at", getattr(obj, "created_at", None) or datetime.now(UTC)),
                setattr(obj, "updated_at", getattr(obj, "updated_at", None) or datetime.now(UTC)),
            )
        )

        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={"name": "Leo", "start_method": "browse"},
        )

        assert response.status_code == 200
        # Field was NOT in request body, so column stays None
        assert mock_user.notification_permission_status is None

    def test_notification_permission_status_invalid_value_rejected(
        self, client, mock_user, mock_db
    ):
        """Only granted/provisional/declined accepted — guard against client bugs."""
        mock_user.has_completed_onboarding = False
        response = client.post(
            "/v1/users/me/complete-onboarding",
            json={
                "name": "Leo",
                "start_method": "browse",
                "notification_permission_status": "unknown",
            },
        )
        assert response.status_code == 422


class TestGetMeShoppingListDefaults:
    """Tests for default shopping list fields in GET /v1/users/me."""

    def test_get_me_includes_shopping_list_defaults(self, client, mock_user, mock_db):
        """Test that default_shopping_list_id and previous_shopping_list_id are in response."""
        mock_db.db.execute.return_value = MockExecuteResult([0])
        response = client.get("/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert "default_shopping_list_id" in data
        assert "previous_shopping_list_id" in data
        assert data["default_shopping_list_id"] is None
        assert data["previous_shopping_list_id"] is None

    def test_get_me_with_shopping_list_defaults_set(self, client, mock_user, mock_db):
        """Test that set default/previous shopping list IDs are returned."""
        list_id = str(uuid.uuid4())
        prev_id = str(uuid.uuid4())
        mock_user.default_shopping_list_id = list_id
        mock_user.previous_shopping_list_id = prev_id
        mock_db.db.execute.return_value = MockExecuteResult([0])
        response = client.get("/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["default_shopping_list_id"] == list_id
        assert data["previous_shopping_list_id"] == prev_id


class TestSetDefaultShoppingList:
    """Tests for PUT /v1/users/me/default-shopping-list."""

    def test_set_default_shopping_list_success(self, client, mock_user, mock_db):
        """Test setting a default shopping list."""
        list_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        from utils.models.shopping_list import ShoppingList
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            "/v1/users/me/default-shopping-list",
            json={"shopping_list_id": list_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_shopping_list_id"] == list_id

    def test_set_default_shifts_previous(self, client, mock_user, mock_db):
        """Test that setting a new default moves old default to previous."""
        old_id = str(uuid.uuid4())
        new_id = str(uuid.uuid4())
        mock_user.default_shopping_list_id = old_id

        sl = MockShoppingList(id=new_id, owner_id=str(mock_user.id))
        from utils.models.shopping_list import ShoppingList
        mock_db.set_find_by(ShoppingList, sl, id=new_id)

        response = client.put(
            "/v1/users/me/default-shopping-list",
            json={"shopping_list_id": new_id},
        )
        assert response.status_code == 200
        assert mock_user.previous_shopping_list_id == old_id
        assert mock_user.default_shopping_list_id == sl.id

    def test_clear_default_shopping_list(self, client, mock_user, mock_db):
        """Test clearing the default shopping list."""
        mock_user.default_shopping_list_id = str(uuid.uuid4())
        mock_user.previous_shopping_list_id = str(uuid.uuid4())

        response = client.put(
            "/v1/users/me/default-shopping-list",
            json={"shopping_list_id": None},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_shopping_list_id"] is None
        assert data["previous_shopping_list_id"] is None
        assert mock_user.default_shopping_list_id is None
        assert mock_user.previous_shopping_list_id is None

    def test_set_default_shopping_list_not_found(self, client, mock_user, mock_db):
        """Test setting a non-existent list as default returns 404."""
        response = client.put(
            "/v1/users/me/default-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_set_default_shopping_list_no_access(self, client, mock_user, mock_db):
        """Test setting a list the user doesn't have access to returns 403."""
        list_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(uuid.uuid4()))
        from utils.models.shopping_list import ShoppingList
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            "/v1/users/me/default-shopping-list",
            json={"shopping_list_id": list_id},
        )
        assert response.status_code == 403

    def test_set_default_same_as_current(self, client, mock_user, mock_db):
        """Test setting the same list as default doesn't change previous."""
        list_id = str(uuid.uuid4())
        mock_user.default_shopping_list_id = list_id
        mock_user.previous_shopping_list_id = None

        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id))
        from utils.models.shopping_list import ShoppingList
        mock_db.set_find_by(ShoppingList, sl, id=list_id)

        response = client.put(
            "/v1/users/me/default-shopping-list",
            json={"shopping_list_id": list_id},
        )
        assert response.status_code == 200
        # Previous should still be None since we set the same list
        assert mock_user.previous_shopping_list_id is None


class TestSetDefaultRecipeBook:
    """Tests for PUT /v1/users/me/default-recipe-book."""

    def test_set_default_recipe_book_success(self, client, mock_user, mock_db):
        """Test setting a default recipe book."""
        from conftest import MockQuery, MockRecipeBook
        book_id = str(uuid.uuid4())
        book = MockRecipeBook(id=book_id)
        from utils.models.recipe_book import RecipeBook
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        # User must be a member — mock query returns a membership
        membership = MockRecipeBookUser(user_id=str(mock_user.id), recipe_book_id=book_id)
        mock_db.db.query.return_value = MockQuery([membership])

        response = client.put(
            "/v1/users/me/default-recipe-book",
            json={"recipe_book_id": book_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_recipe_book_id"] == book_id

    def test_set_default_shifts_previous(self, client, mock_user, mock_db):
        """Test that setting a new default moves old to previous."""
        from conftest import MockQuery, MockRecipeBook
        old_id = str(uuid.uuid4())
        new_id = str(uuid.uuid4())
        mock_user.default_recipe_book_id = old_id

        book = MockRecipeBook(id=new_id)
        from utils.models.recipe_book import RecipeBook
        mock_db.set_find_by(RecipeBook, book, id=new_id)
        membership = MockRecipeBookUser(user_id=str(mock_user.id), recipe_book_id=new_id)
        mock_db.db.query.return_value = MockQuery([membership])

        response = client.put(
            "/v1/users/me/default-recipe-book",
            json={"recipe_book_id": new_id},
        )
        assert response.status_code == 200
        assert mock_user.previous_recipe_book_id == old_id

    def test_clear_default_recipe_book(self, client, mock_user, mock_db):
        """Test clearing the default recipe book."""
        mock_user.default_recipe_book_id = str(uuid.uuid4())
        mock_user.previous_recipe_book_id = str(uuid.uuid4())

        response = client.put(
            "/v1/users/me/default-recipe-book",
            json={"recipe_book_id": None},
        )
        assert response.status_code == 200
        assert mock_user.default_recipe_book_id is None
        assert mock_user.previous_recipe_book_id is None

    def test_set_default_recipe_book_not_found(self, client, mock_user, mock_db):
        """Test setting a non-existent book returns 404."""
        response = client.put(
            "/v1/users/me/default-recipe-book",
            json={"recipe_book_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_set_default_recipe_book_not_member(self, client, mock_user, mock_db):
        """Test setting a book the user is not a member of returns 403 (line 51)."""
        from conftest import MockQuery, MockRecipeBook
        book_id = str(uuid.uuid4())
        book = MockRecipeBook(id=book_id)
        from utils.models.recipe_book import RecipeBook
        mock_db.set_find_by(RecipeBook, book, id=book_id)
        # User is NOT a member — query returns empty
        mock_db.db.query.return_value = MockQuery([])

        response = client.put(
            "/v1/users/me/default-recipe-book",
            json={"recipe_book_id": book_id},
        )
        assert response.status_code == 403

    def test_get_me_includes_previous_recipe_book_id(self, client, mock_user, mock_db):
        """Test that GET /me returns previous_recipe_book_id."""
        prev_id = str(uuid.uuid4())
        mock_user.previous_recipe_book_id = prev_id
        mock_db.db.execute.return_value = MockExecuteResult([0])
        response = client.get("/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["previous_recipe_book_id"] == prev_id


class TestRecordClientError:
    """Tests for POST /v1/users/me/client-errors."""

    def test_minimal_payload_writes_row(self, client, mock_user, mock_db):
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/client-errors",
            json={
                "error_type": "StateError",
                "error_message": "FCM token null after granted permission",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["recorded"] is True

        added = [c.args[0] for c in mock_db.db.add.call_args_list]
        rows = [r for r in added if type(r).__name__ == "ErrorLog"]
        assert len(rows) == 1
        row = rows[0]
        assert row.service == "client"
        assert row.user_id == mock_user.id
        assert row.error_type == "StateError"
        assert row.error_message == "FCM token null after granted permission"
        assert row.stack_trace is None
        assert row.method is None
        assert row.path is None
        assert row.status_code is None

    def test_area_operation_extras_serialised_to_stack_trace(
        self, client, mock_user, mock_db,
    ):
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/client-errors",
            json={
                "error_type": "PlatformException",
                "error_message": "APNs registration failed",
                "area": "push",
                "operation": "apns.registrationFailed",
                "extras": {"platform": "ios", "auth_status": "authorized"},
            },
        )
        assert response.status_code == 200

        rows = [
            c.args[0] for c in mock_db.db.add.call_args_list
            if type(c.args[0]).__name__ == "ErrorLog"
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row.stack_trace is not None
        import json as _json
        envelope = _json.loads(row.stack_trace)
        assert envelope["area"] == "push"
        assert envelope["operation"] == "apns.registrationFailed"
        assert envelope["extras"]["platform"] == "ios"
        assert envelope["extras"]["auth_status"] == "authorized"

    def test_dio_extras_hoisted_to_first_class_columns(
        self, client, mock_user, mock_db,
    ):
        """http.method and http.path in extras land as method/path for rollups."""
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/client-errors",
            json={
                "error_type": "DioException",
                "error_message": "POST /v1/users/me/push-tokens → 500",
                "area": "push",
                "operation": "registerToken.backend",
                "extras": {
                    "http.method": "POST",
                    "http.path": "/v1/users/me/push-tokens",
                    "platform": "ios",
                },
                "status_code": 500,
            },
        )
        assert response.status_code == 200

        rows = [
            c.args[0] for c in mock_db.db.add.call_args_list
            if type(c.args[0]).__name__ == "ErrorLog"
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row.method == "POST"
        assert row.path == "/v1/users/me/push-tokens"
        assert row.status_code == 500

    def test_missing_required_fields_rejected(self, client, mock_user, mock_db):
        response = client.post(
            "/v1/users/me/client-errors",
            json={"error_message": "missing error_type"},
        )
        assert response.status_code == 422

    def test_extra_fields_rejected(self, client, mock_user, mock_db):
        """extra='forbid' blocks unknown keys (no smuggling arbitrary columns)."""
        response = client.post(
            "/v1/users/me/client-errors",
            json={
                "error_type": "X",
                "error_message": "Y",
                "service": "api",  # attempt to spoof service
            },
        )
        assert response.status_code == 422

    def test_long_fields_truncated(self, client, mock_user, mock_db):
        """Fields exceeding Pydantic max_length return 422 (enforced by caller)."""
        mock_db.db.commit = MagicMock()
        # error_type over 120 chars → 422 at validation
        response = client.post(
            "/v1/users/me/client-errors",
            json={"error_type": "x" * 121, "error_message": "msg"},
        )
        assert response.status_code == 422

    def test_empty_extras_no_stack_trace(self, client, mock_user, mock_db):
        """No area/operation/extras → stack_trace stays None."""
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/client-errors",
            json={"error_type": "ClientLog", "error_message": "hello"},
        )
        assert response.status_code == 200
        rows = [
            c.args[0] for c in mock_db.db.add.call_args_list
            if type(c.args[0]).__name__ == "ErrorLog"
        ]
        assert rows[0].stack_trace is None

    def test_long_error_message_truncated_to_limit(
        self, client, mock_user, mock_db,
    ):
        """Valid-but-at-limit message stored, over-limit rejected at validation."""
        mock_db.db.commit = MagicMock()
        # 2000 chars is the max allowed — should succeed.
        at_limit = "a" * 2000
        response = client.post(
            "/v1/users/me/client-errors",
            json={"error_type": "X", "error_message": at_limit},
        )
        assert response.status_code == 200
        rows = [
            c.args[0] for c in mock_db.db.add.call_args_list
            if type(c.args[0]).__name__ == "ErrorLog"
        ]
        assert rows[0].error_message == at_limit
        assert len(rows[0].error_message) == 2000

    def test_non_string_http_extras_ignored(self, client, mock_user, mock_db):
        """Garbage types in http.method/http.path don't populate method/path."""
        mock_db.db.commit = MagicMock()
        response = client.post(
            "/v1/users/me/client-errors",
            json={
                "error_type": "X",
                "error_message": "Y",
                "extras": {"http.method": 42, "http.path": {"nested": True}},
            },
        )
        assert response.status_code == 200
        rows = [
            c.args[0] for c in mock_db.db.add.call_args_list
            if type(c.args[0]).__name__ == "ErrorLog"
        ]
        assert rows[0].method is None
        assert rows[0].path is None
