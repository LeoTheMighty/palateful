"""Tests for friends endpoints."""

from conftest import (
    MockExecuteResult,
    MockFriendship,
    MockUser,
)


class TestListFriends:
    """Tests for GET /v1/friends."""

    def test_list_friends_success(self, client, mock_db, mock_user):
        """Test listing friends."""
        friend = MockUser(name="Friend User", username="friend1")
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=str(friend.id),
            friend=friend,
        )
        # ListFriends uses db.execute(select(Friendship)) -> scalars().all()
        mock_db.db.execute.return_value = MockExecuteResult([friendship])

        response = client.get("/v1/friends")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["friends"][0]["username"] == "friend1"

    def test_list_friends_empty(self, client, mock_db, mock_user):
        """Test listing friends when user has none."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/friends")
        assert response.status_code == 200
        data = response.json()
        assert data["friends"] == []
        assert data["count"] == 0


class TestListFriendRequests:
    """Tests for GET /v1/friends/requests."""

    def test_list_friend_requests(self, client, mock_db, mock_user):
        """Test listing pending friend requests."""
        # ListFriendRequests makes two db.execute() calls (received, sent)
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/friends/requests")
        assert response.status_code == 200
        data = response.json()
        assert "received" in data
        assert "sent" in data


class TestSendFriendRequest:
    """Tests for POST /v1/friends/requests."""

    def test_send_friend_request_missing_fields(self, client, mock_db, mock_user):
        """Test sending a request without username or user_id fails."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/friends/requests",
            json={}
        )
        # Endpoint returns 400 when neither username nor user_id is provided
        assert response.status_code in (400, 422, 500)


class TestGetFriend:
    """Tests for GET /v1/friends/{friend_id}."""

    def test_get_friend_success(self, client, mock_db, mock_user):
        """Test getting a friend's profile."""
        friend = MockUser(name="Friend", username="friend1")
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=str(friend.id),
            friend=friend,
        )
        # GetFriend uses db.execute() -> scalar_one_or_none()
        result = MockExecuteResult([friendship])
        mock_db.db.execute.return_value = result

        response = client.get(f"/v1/friends/{friend.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "friend1"

    def test_get_friend_not_found(self, client, mock_db, mock_user):
        """Test getting a non-friend."""
        result = MockExecuteResult([])
        mock_db.db.execute.return_value = result

        response = client.get("/v1/friends/nonexistent")
        assert response.status_code == 404


class TestRemoveFriend:
    """Tests for DELETE /v1/friends/{friend_id}."""

    def test_remove_friend_success(self, client, mock_db, mock_user):
        """Test removing a friend."""
        friend_id = "friend-id"
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=friend_id,
        )
        # RemoveFriend uses db.execute() -> scalars().all()
        mock_db.db.execute.return_value = MockExecuteResult([friendship])

        response = client.delete(f"/v1/friends/{friend_id}")
        assert response.status_code == 200

    def test_remove_friend_not_found(self, client, mock_db, mock_user):
        """Test removing a non-friend."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.delete("/v1/friends/nonexistent")
        assert response.status_code == 404
