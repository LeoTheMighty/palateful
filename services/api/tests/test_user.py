"""Tests for user endpoints."""

import uuid
from unittest.mock import MagicMock

from conftest import MockExecuteResult, MockUser


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


class TestNotificationPreferences:
    """Tests for notification preference endpoints."""

    def test_get_notification_preferences(self, client, mock_user, mock_db):
        """Test getting notification preferences."""
        response = client.get("/v1/users/me/notification-preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["push_enabled"] is True
        assert "timezone" in data

    def test_update_notification_preferences(self, client, mock_user, mock_db):
        """Test updating notification preferences."""
        mock_db.db.commit = MagicMock()
        mock_db.db.refresh = MagicMock()
        response = client.put(
            "/v1/users/me/notification-preferences",
            json={"push_enabled": False}
        )
        assert response.status_code == 200


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
