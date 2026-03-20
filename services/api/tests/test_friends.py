"""Tests for friends endpoints."""

import uuid
from unittest.mock import MagicMock, patch

from conftest import (
    MockExecuteResult,
    MockFriendRequest,
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
        assert response.status_code == 400

    @patch("api.v1.friends.send_request.get_push_service")
    def test_send_request_by_username_success(self, mock_push, client, mock_db, mock_user):
        """Test sending a friend request by username succeeds."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service

        target = MockUser(username="targetuser", name="Target")

        # 1) find user by username -> target
        # 2) check existing friendship -> None
        # 3) check existing pending request -> None
        # 4) check rate limit -> 0
        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),      # select User by username
            MockExecuteResult([]),            # select Friendship (not friends)
            MockExecuteResult([]),            # select FriendRequest (no pending)
            MockExecuteResult([0]),           # count requests today = 0
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "targetuser"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["to_user"]["username"] == "targetuser"
        mock_service.send_to_user.assert_called_once()

    @patch("api.v1.friends.send_request.get_push_service")
    def test_send_request_by_username_with_at_prefix(self, mock_push, client, mock_db, mock_user):
        """Test sending a friend request with @-prefixed username strips the @."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service

        target = MockUser(username="targetuser", name="Target")

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "@targetuser"},
        )
        assert response.status_code == 200

    @patch("api.v1.friends.send_request.get_push_service")
    def test_send_request_by_user_id_success(self, mock_push, client, mock_db, mock_user):
        """Test sending a friend request by user_id succeeds."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service

        target_id = str(uuid.uuid4())
        target = MockUser(id=target_id, username="target", name="Target")

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),      # select User by id
            MockExecuteResult([]),            # no existing friendship
            MockExecuteResult([]),            # no pending request
            MockExecuteResult([0]),           # rate limit count
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"user_id": target_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["to_user"]["id"] == target_id

    def test_send_request_by_username_not_found(self, client, mock_db, mock_user):
        """Test sending a request to a nonexistent username returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/friends/requests",
            json={"username": "nobody"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_send_request_by_user_id_not_found(self, client, mock_db, mock_user):
        """Test sending a request to a nonexistent user_id returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/friends/requests",
            json={"user_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_send_request_to_self(self, client, mock_db, mock_user):
        """Test cannot send a friend request to yourself."""
        # Return mock_user itself as the target
        mock_db.db.execute.return_value = MockExecuteResult([mock_user])

        response = client.post(
            "/v1/friends/requests",
            json={"username": mock_user.username},
        )
        assert response.status_code == 400
        data = response.json()
        assert "yourself" in data["error_message"].lower()

    def test_send_request_already_friends(self, client, mock_db, mock_user):
        """Test cannot send request if already friends."""
        target = MockUser(username="buddy", name="Buddy")
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=str(target.id),
        )

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),        # find target user
            MockExecuteResult([friendship]),    # existing friendship found
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "buddy"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "already friends" in data["error_message"].lower()

    def test_send_request_pending_outgoing_exists(self, client, mock_db, mock_user):
        """Test cannot send request if already sent one to this user."""
        target = MockUser(username="buddy", name="Buddy")
        existing_req = MockFriendRequest(
            from_user_id=str(mock_user.id),
            to_user_id=str(target.id),
            status="pending",
        )

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),         # find target user
            MockExecuteResult([]),               # no existing friendship
            MockExecuteResult([existing_req]),   # existing pending request from us
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "buddy"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "already have a pending" in data["error_message"].lower()

    def test_send_request_pending_incoming_exists(self, client, mock_db, mock_user):
        """Test cannot send request if target already sent one to us."""
        target = MockUser(username="buddy", name="Buddy")
        existing_req = MockFriendRequest(
            from_user_id=str(target.id),
            to_user_id=str(mock_user.id),
            status="pending",
        )

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),         # find target user
            MockExecuteResult([]),               # no existing friendship
            MockExecuteResult([existing_req]),   # existing pending request from them
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "buddy"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "accept it instead" in data["error_message"].lower()

    def test_send_request_rate_limited(self, client, mock_db, mock_user):
        """Test rate limit prevents sending too many requests."""
        target = MockUser(username="buddy", name="Buddy")

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),    # find target user
            MockExecuteResult([]),          # no existing friendship
            MockExecuteResult([]),          # no pending request
            MockExecuteResult([20]),        # rate limit hit (20 requests today)
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "buddy"},
        )
        assert response.status_code == 429
        data = response.json()
        assert "20" in data["error_message"]

    @patch("api.v1.friends.send_request.get_push_service")
    def test_send_request_display_name_with_username(self, mock_push, client, mock_db, mock_user):
        """Test push notification uses @username when available."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service
        mock_user.username = "sender"
        mock_user.name = "Sender Name"

        target = MockUser(username="target", name="Target")

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "target"},
        )
        assert response.status_code == 200
        # Verify the notification body contains @sender
        call_args = mock_service.send_to_user.call_args
        notification = call_args[0][1]
        assert "@sender" in notification.body

    @patch("api.v1.friends.send_request.get_push_service")
    def test_send_request_display_name_no_username_uses_name(self, mock_push, client, mock_db, mock_user):
        """Test push notification uses name when username is None."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service
        mock_user.username = None
        mock_user.name = "Sender Name"

        target = MockUser(username="target", name="Target")

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "target"},
        )
        assert response.status_code == 200
        call_args = mock_service.send_to_user.call_args
        notification = call_args[0][1]
        assert "Sender Name" in notification.body

    @patch("api.v1.friends.send_request.get_push_service")
    def test_send_request_display_name_no_username_no_name(self, mock_push, client, mock_db, mock_user):
        """Test push notification uses 'Someone' when both username and name are None."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service
        mock_user.username = None
        mock_user.name = None

        target = MockUser(username="target", name="Target")

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "target"},
        )
        assert response.status_code == 200
        call_args = mock_service.send_to_user.call_args
        notification = call_args[0][1]
        assert "Someone" in notification.body

    @patch("api.v1.friends.send_request.get_push_service")
    def test_send_request_with_message(self, mock_push, client, mock_db, mock_user):
        """Test sending a friend request with an optional message."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service

        target = MockUser(username="target", name="Target")

        mock_db.db.execute.side_effect = [
            MockExecuteResult([target]),
            MockExecuteResult([]),
            MockExecuteResult([]),
            MockExecuteResult([0]),
        ]

        response = client.post(
            "/v1/friends/requests",
            json={"username": "target", "message": "Let's cook together!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestAcceptFriendRequest:
    """Tests for POST /v1/friends/requests/{request_id}/accept."""

    @patch("api.v1.friends.accept_request.get_push_service")
    def test_accept_request_success(self, mock_push, client, mock_db, mock_user):
        """Test accepting a friend request succeeds."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service

        request_id = str(uuid.uuid4())
        from_user = MockUser(username="requester", name="Requester", picture="pic.jpg")
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(from_user.id),
            to_user_id=str(mock_user.id),
            status="pending",
            from_user=from_user,
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["friend"]["username"] == "requester"
        assert data["friend"]["name"] == "Requester"
        assert data["friend"]["picture"] == "pic.jpg"
        assert data["friend"]["id"] == str(from_user.id)

        # Verify status was updated
        assert friend_request.status == "accepted"

        # Verify two friendships were created (bidirectional)
        assert mock_db.db.add.call_count == 2

        # Verify push notification was sent
        mock_service.send_to_user.assert_called_once()

    def test_accept_request_not_found(self, client, mock_db, mock_user):
        """Test accepting a nonexistent request returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.post("/v1/friends/requests/nonexistent/accept")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_accept_request_wrong_user(self, client, mock_db, mock_user):
        """Test cannot accept a request not addressed to you."""
        request_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=other_user_id,  # sent to someone else
            status="pending",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 403
        data = response.json()
        assert "sent to you" in data["error_message"].lower()

    def test_accept_request_already_accepted(self, client, mock_db, mock_user):
        """Test cannot accept an already accepted request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="accepted",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 400
        data = response.json()
        assert "already been accepted" in data["error_message"].lower()

    def test_accept_request_already_declined(self, client, mock_db, mock_user):
        """Test cannot accept an already declined request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="declined",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 400
        data = response.json()
        assert "already been declined" in data["error_message"].lower()

    @patch("api.v1.friends.accept_request.get_push_service")
    def test_accept_request_display_name_with_username(self, mock_push, client, mock_db, mock_user):
        """Test push notification uses @username when available."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service
        mock_user.username = "accepter"
        mock_user.name = "Accepter Name"

        request_id = str(uuid.uuid4())
        from_user = MockUser(username="requester", name="Requester")
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(from_user.id),
            to_user_id=str(mock_user.id),
            status="pending",
            from_user=from_user,
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 200
        call_args = mock_service.send_to_user.call_args
        notification = call_args[0][1]
        assert "@accepter" in notification.body

    @patch("api.v1.friends.accept_request.get_push_service")
    def test_accept_request_display_name_no_username_uses_name(self, mock_push, client, mock_db, mock_user):
        """Test push notification uses name when username is None."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service
        mock_user.username = None
        mock_user.name = "Accepter Name"

        request_id = str(uuid.uuid4())
        from_user = MockUser(username="requester", name="Requester")
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(from_user.id),
            to_user_id=str(mock_user.id),
            status="pending",
            from_user=from_user,
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 200
        call_args = mock_service.send_to_user.call_args
        notification = call_args[0][1]
        assert "Accepter Name" in notification.body

    @patch("api.v1.friends.accept_request.get_push_service")
    def test_accept_request_display_name_no_username_no_name(self, mock_push, client, mock_db, mock_user):
        """Test push notification uses 'Someone' when both username and name are None."""
        mock_service = MagicMock()
        mock_push.return_value = mock_service
        mock_user.username = None
        mock_user.name = None

        request_id = str(uuid.uuid4())
        from_user = MockUser(username="requester", name="Requester")
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(from_user.id),
            to_user_id=str(mock_user.id),
            status="pending",
            from_user=from_user,
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 200
        call_args = mock_service.send_to_user.call_args
        notification = call_args[0][1]
        assert "Someone" in notification.body


class TestDeclineFriendRequest:
    """Tests for POST /v1/friends/requests/{request_id}/decline."""

    def test_decline_request_success(self, client, mock_db, mock_user):
        """Test declining a friend request succeeds."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="pending",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Friend request declined"

        # Verify status was updated
        assert friend_request.status == "declined"

    def test_decline_request_not_found(self, client, mock_db, mock_user):
        """Test declining a nonexistent request returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.post("/v1/friends/requests/nonexistent/decline")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_decline_request_wrong_user(self, client, mock_db, mock_user):
        """Test cannot decline a request not addressed to you."""
        request_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=other_user_id,  # sent to someone else
            status="pending",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 403
        data = response.json()
        assert "sent to you" in data["error_message"].lower()

    def test_decline_request_already_accepted(self, client, mock_db, mock_user):
        """Test cannot decline an already accepted request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="accepted",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 400
        data = response.json()
        assert "already been accepted" in data["error_message"].lower()

    def test_decline_request_already_declined(self, client, mock_db, mock_user):
        """Test cannot decline an already declined request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="declined",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 400
        data = response.json()
        assert "already been declined" in data["error_message"].lower()


class TestCancelFriendRequest:
    """Tests for DELETE /v1/friends/requests/{request_id}."""

    def test_cancel_request_success(self, client, mock_db, mock_user):
        """Test cancelling a friend request succeeds."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(mock_user.id),
            to_user_id=str(uuid.uuid4()),
            status="pending",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Friend request cancelled"

        # Verify the request was deleted
        mock_db.db.delete.assert_called_once_with(friend_request)
        mock_db.db.commit.assert_called()

    def test_cancel_request_not_found(self, client, mock_db, mock_user):
        """Test cancelling a nonexistent request returns 404."""
        mock_db.db.execute.return_value = MockExecuteResult([])

        response = client.delete("/v1/friends/requests/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_cancel_request_wrong_user(self, client, mock_db, mock_user):
        """Test cannot cancel a request you did not send."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),  # someone else sent this
            to_user_id=str(uuid.uuid4()),
            status="pending",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 403
        data = response.json()
        assert "you sent" in data["error_message"].lower()

    def test_cancel_request_already_accepted(self, client, mock_db, mock_user):
        """Test cannot cancel an already accepted request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(mock_user.id),
            to_user_id=str(uuid.uuid4()),
            status="accepted",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 400
        data = response.json()
        assert "already been accepted" in data["error_message"].lower()

    def test_cancel_request_already_declined(self, client, mock_db, mock_user):
        """Test cannot cancel an already declined request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(mock_user.id),
            to_user_id=str(uuid.uuid4()),
            status="declined",
        )

        mock_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 400
        data = response.json()
        assert "already been declined" in data["error_message"].lower()


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
