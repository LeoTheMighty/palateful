"""Tests for friends endpoints (aam-28: AsyncEndpoint).

Endpoints converted to `AsyncEndpoint` in aam-28; tests drive the router
via the sync `client` fixture (async deps already overridden in conftest)
and configure `mock_async_db.db.execute.{return_value,side_effect}` on
`AsyncMock`s instead of the legacy `mock_db.db.query` pattern.

Push-notification fan-out is patched at the import site in
`api.v1.friends.send_request` and `api.v1.friends.accept_request` —
those modules now `from api.v1.friends.notifications import
notify_friend_request_sent / notify_friend_request_accepted`, then call
`notify_via_threadpool(helper, ...)` which dispatches the helper on a
sync `Database` in the threadpool. Patching the helper at the import
site replaces the reference passed to the bridge, so the mock receives
the call without any real `send_to_user` work.
"""

import uuid
from unittest.mock import patch

from conftest import (
    MockExecuteResult,
    MockFriendRequest,
    MockFriendship,
    MockUser,
)


class TestListFriends:
    """Tests for GET /v1/friends."""

    def test_list_friends_success(self, client, mock_async_db, mock_user):
        """Test listing friends."""
        friend = MockUser(name="Friend User", username="friend1")
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=str(friend.id),
            friend=friend,
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([friendship])

        response = client.get("/v1/friends")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["friends"][0]["username"] == "friend1"

    def test_list_friends_empty(self, client, mock_async_db, mock_user):
        """Test listing friends when user has none."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/friends")
        assert response.status_code == 200
        data = response.json()
        assert data["friends"] == []
        assert data["count"] == 0


class TestListFriendRequests:
    """Tests for GET /v1/friends/requests."""

    def test_list_friend_requests(self, client, mock_async_db, mock_user):
        """Test listing pending friend requests."""
        # Two execute calls (received, sent); same empty result is fine.
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/friends/requests")
        assert response.status_code == 200
        data = response.json()
        assert "received" in data
        assert "sent" in data


class TestSendFriendRequest:
    """Tests for POST /v1/friends/requests."""

    def test_send_friend_request_missing_fields(
        self, client, mock_async_db, mock_user
    ):
        """Test sending a request without username or user_id fails."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post("/v1/friends/requests", json={})
        assert response.status_code == 400

    @patch("api.v1.friends.send_request.notify_friend_request_sent")
    def test_send_request_by_username_success(
        self, mock_notify, client, mock_async_db, mock_user
    ):
        """Test sending a friend request by username succeeds."""
        target = MockUser(username="targetuser", name="Target")

        mock_async_db.db.execute.side_effect = [
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
        mock_notify.assert_called_once()

    @patch("api.v1.friends.send_request.notify_friend_request_sent")
    def test_send_request_by_username_with_at_prefix(
        self, mock_notify, client, mock_async_db, mock_user
    ):
        """Test sending a friend request with @-prefixed username strips the @."""
        target = MockUser(username="targetuser", name="Target")

        mock_async_db.db.execute.side_effect = [
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

    @patch("api.v1.friends.send_request.notify_friend_request_sent")
    def test_send_request_by_user_id_success(
        self, mock_notify, client, mock_async_db, mock_user
    ):
        """Test sending a friend request by user_id succeeds."""
        target_id = str(uuid.uuid4())
        target = MockUser(id=target_id, username="target", name="Target")

        mock_async_db.db.execute.side_effect = [
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

    def test_send_request_by_username_not_found(
        self, client, mock_async_db, mock_user
    ):
        """Test sending a request to a nonexistent username returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/friends/requests",
            json={"username": "nobody"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_send_request_by_user_id_not_found(
        self, client, mock_async_db, mock_user
    ):
        """Test sending a request to a nonexistent user_id returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post(
            "/v1/friends/requests",
            json={"user_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_send_request_to_self(self, client, mock_async_db, mock_user):
        """Test cannot send a friend request to yourself."""
        mock_async_db.db.execute.return_value = MockExecuteResult([mock_user])

        response = client.post(
            "/v1/friends/requests",
            json={"username": mock_user.username},
        )
        assert response.status_code == 400
        data = response.json()
        assert "yourself" in data["error_message"].lower()

    def test_send_request_already_friends(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot send request if already friends."""
        target = MockUser(username="buddy", name="Buddy")
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=str(target.id),
        )

        mock_async_db.db.execute.side_effect = [
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

    def test_send_request_pending_outgoing_exists(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot send request if already sent one to this user."""
        target = MockUser(username="buddy", name="Buddy")
        existing_req = MockFriendRequest(
            from_user_id=str(mock_user.id),
            to_user_id=str(target.id),
            status="pending",
        )

        mock_async_db.db.execute.side_effect = [
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

    def test_send_request_pending_incoming_exists(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot send request if target already sent one to us."""
        target = MockUser(username="buddy", name="Buddy")
        existing_req = MockFriendRequest(
            from_user_id=str(target.id),
            to_user_id=str(mock_user.id),
            status="pending",
        )

        mock_async_db.db.execute.side_effect = [
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

    def test_send_request_rate_limited(
        self, client, mock_async_db, mock_user
    ):
        """Test rate limit prevents sending too many requests."""
        target = MockUser(username="buddy", name="Buddy")

        mock_async_db.db.execute.side_effect = [
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

    @patch("api.v1.friends.send_request.notify_friend_request_sent")
    def test_send_request_with_message(
        self, mock_notify, client, mock_async_db, mock_user
    ):
        """Test sending a friend request with an optional message."""
        target = MockUser(username="target", name="Target")

        mock_async_db.db.execute.side_effect = [
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


class TestNotifyFriendRequestSent:
    """Tests for the sync notify_friend_request_sent helper.

    The async endpoint dispatches notification copy via this sync helper
    inside the threadpool; the helper is exercised directly to cover the
    `_display_name` branches that the endpoint tests previously inlined.
    """

    @patch("api.v1.friends.notifications.get_push_service")
    def test_notify_uses_at_username_when_present(self, mock_push):
        """Push body uses @username when sender has one."""
        from unittest.mock import MagicMock

        from api.v1.friends.notifications import notify_friend_request_sent

        mock_service = MagicMock()
        mock_push.return_value = mock_service
        sender = MockUser(username="sender", name="Sender Name")
        target = MockUser(username="target")
        database = MagicMock()
        database.db.query.return_value.filter.return_value.first.return_value = target

        notify_friend_request_sent(
            target_user_id=str(target.id),
            friend_request_id="req-1",
            sender=sender,
            database=database,
        )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "@sender" in notification.body

    @patch("api.v1.friends.notifications.get_push_service")
    def test_notify_uses_name_when_no_username(self, mock_push):
        """Push body falls back to name when username is None."""
        from unittest.mock import MagicMock

        from api.v1.friends.notifications import notify_friend_request_sent

        mock_service = MagicMock()
        mock_push.return_value = mock_service
        sender = MockUser(username=None, name="Sender Name")
        target = MockUser(username="target")
        database = MagicMock()
        database.db.query.return_value.filter.return_value.first.return_value = target

        notify_friend_request_sent(
            target_user_id=str(target.id),
            friend_request_id="req-1",
            sender=sender,
            database=database,
        )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Sender Name" in notification.body

    @patch("api.v1.friends.notifications.get_push_service")
    def test_notify_uses_someone_when_no_username_no_name(self, mock_push):
        """Push body uses 'Someone' when both username and name are None."""
        from unittest.mock import MagicMock

        from api.v1.friends.notifications import notify_friend_request_sent

        mock_service = MagicMock()
        mock_push.return_value = mock_service
        sender = MockUser(username=None, name=None)
        target = MockUser(username="target")
        database = MagicMock()
        database.db.query.return_value.filter.return_value.first.return_value = target

        notify_friend_request_sent(
            target_user_id=str(target.id),
            friend_request_id="req-1",
            sender=sender,
            database=database,
        )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Someone" in notification.body


class TestAcceptFriendRequest:
    """Tests for POST /v1/friends/requests/{request_id}/accept."""

    @patch("api.v1.friends.accept_request.notify_friend_request_accepted")
    def test_accept_request_success(
        self, mock_notify, client, mock_async_db, mock_user
    ):
        """Test accepting a friend request succeeds."""
        request_id = str(uuid.uuid4())
        from_user = MockUser(username="requester", name="Requester", picture="pic.jpg")
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(from_user.id),
            to_user_id=str(mock_user.id),
            status="pending",
            from_user=from_user,
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["friend"]["username"] == "requester"
        assert data["friend"]["name"] == "Requester"
        assert data["friend"]["picture"] == "pic.jpg"
        assert data["friend"]["id"] == str(from_user.id)

        # Status was mutated and bidirectional friendships were added.
        assert friend_request.status == "accepted"
        assert mock_async_db.db.add.call_count == 2
        mock_notify.assert_called_once()

    def test_accept_request_not_found(
        self, client, mock_async_db, mock_user
    ):
        """Test accepting a nonexistent request returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post("/v1/friends/requests/nonexistent/accept")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_accept_request_wrong_user(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot accept a request not addressed to you."""
        request_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=other_user_id,
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 403
        data = response.json()
        assert "sent to you" in data["error_message"].lower()

    def test_accept_request_already_accepted(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot accept an already accepted request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="accepted",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 400
        data = response.json()
        assert "already been accepted" in data["error_message"].lower()

    def test_accept_request_already_declined(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot accept an already declined request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="declined",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/accept")
        assert response.status_code == 400
        data = response.json()
        assert "already been declined" in data["error_message"].lower()


class TestNotifyFriendRequestAccepted:
    """Tests for the sync notify_friend_request_accepted helper."""

    @patch("api.v1.friends.notifications.get_push_service")
    def test_notify_uses_at_username_when_present(self, mock_push):
        """Push body uses @username when accepter has one."""
        from unittest.mock import MagicMock

        from api.v1.friends.notifications import notify_friend_request_accepted

        mock_service = MagicMock()
        mock_push.return_value = mock_service
        accepter = MockUser(username="accepter", name="Accepter Name")
        requester = MockUser(username="req")
        database = MagicMock()
        database.db.query.return_value.filter.return_value.first.return_value = (
            requester
        )

        notify_friend_request_accepted(
            requester_id=str(requester.id),
            accepter=accepter,
            database=database,
        )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "@accepter" in notification.body

    @patch("api.v1.friends.notifications.get_push_service")
    def test_notify_uses_name_when_no_username(self, mock_push):
        """Push body falls back to name when username is None."""
        from unittest.mock import MagicMock

        from api.v1.friends.notifications import notify_friend_request_accepted

        mock_service = MagicMock()
        mock_push.return_value = mock_service
        accepter = MockUser(username=None, name="Accepter Name")
        requester = MockUser(username="req")
        database = MagicMock()
        database.db.query.return_value.filter.return_value.first.return_value = (
            requester
        )

        notify_friend_request_accepted(
            requester_id=str(requester.id),
            accepter=accepter,
            database=database,
        )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Accepter Name" in notification.body

    @patch("api.v1.friends.notifications.get_push_service")
    def test_notify_uses_someone_when_no_username_no_name(self, mock_push):
        """Push body uses 'Someone' when both username and name are None."""
        from unittest.mock import MagicMock

        from api.v1.friends.notifications import notify_friend_request_accepted

        mock_service = MagicMock()
        mock_push.return_value = mock_service
        accepter = MockUser(username=None, name=None)
        requester = MockUser(username="req")
        database = MagicMock()
        database.db.query.return_value.filter.return_value.first.return_value = (
            requester
        )

        notify_friend_request_accepted(
            requester_id=str(requester.id),
            accepter=accepter,
            database=database,
        )

        notification = mock_service.send_to_user.call_args[0][1]
        assert "Someone" in notification.body


class TestDeclineFriendRequest:
    """Tests for POST /v1/friends/requests/{request_id}/decline."""

    def test_decline_request_success(
        self, client, mock_async_db, mock_user
    ):
        """Test declining a friend request succeeds."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Friend request declined"
        assert friend_request.status == "declined"

    def test_decline_request_not_found(
        self, client, mock_async_db, mock_user
    ):
        """Test declining a nonexistent request returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.post("/v1/friends/requests/nonexistent/decline")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_decline_request_wrong_user(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot decline a request not addressed to you."""
        request_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=other_user_id,
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 403
        data = response.json()
        assert "sent to you" in data["error_message"].lower()

    def test_decline_request_already_accepted(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot decline an already accepted request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="accepted",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 400
        data = response.json()
        assert "already been accepted" in data["error_message"].lower()

    def test_decline_request_already_declined(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot decline an already declined request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(mock_user.id),
            status="declined",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.post(f"/v1/friends/requests/{request_id}/decline")
        assert response.status_code == 400
        data = response.json()
        assert "already been declined" in data["error_message"].lower()


class TestCancelFriendRequest:
    """Tests for DELETE /v1/friends/requests/{request_id}."""

    def test_cancel_request_success(
        self, client, mock_async_db, mock_user
    ):
        """Test cancelling a friend request succeeds."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(mock_user.id),
            to_user_id=str(uuid.uuid4()),
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Friend request cancelled"

        mock_async_db.db.delete.assert_awaited_once_with(friend_request)
        mock_async_db.db.commit.assert_awaited()

    def test_cancel_request_not_found(
        self, client, mock_async_db, mock_user
    ):
        """Test cancelling a nonexistent request returns 404."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.delete("/v1/friends/requests/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error_message"].lower()

    def test_cancel_request_wrong_user(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot cancel a request you did not send."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(uuid.uuid4()),
            to_user_id=str(uuid.uuid4()),
            status="pending",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 403
        data = response.json()
        assert "you sent" in data["error_message"].lower()

    def test_cancel_request_already_accepted(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot cancel an already accepted request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(mock_user.id),
            to_user_id=str(uuid.uuid4()),
            status="accepted",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 400
        data = response.json()
        assert "already been accepted" in data["error_message"].lower()

    def test_cancel_request_already_declined(
        self, client, mock_async_db, mock_user
    ):
        """Test cannot cancel an already declined request."""
        request_id = str(uuid.uuid4())
        friend_request = MockFriendRequest(
            id=request_id,
            from_user_id=str(mock_user.id),
            to_user_id=str(uuid.uuid4()),
            status="declined",
        )

        mock_async_db.db.execute.return_value = MockExecuteResult([friend_request])

        response = client.delete(f"/v1/friends/requests/{request_id}")
        assert response.status_code == 400
        data = response.json()
        assert "already been declined" in data["error_message"].lower()


class TestGetFriend:
    """Tests for GET /v1/friends/{friend_id}."""

    def test_get_friend_success(self, client, mock_async_db, mock_user):
        """Test getting a friend's profile."""
        friend = MockUser(name="Friend", username="friend1")
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=str(friend.id),
            friend=friend,
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([friendship])

        response = client.get(f"/v1/friends/{friend.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "friend1"

    def test_get_friend_not_found(self, client, mock_async_db, mock_user):
        """Test getting a non-friend."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.get("/v1/friends/nonexistent")
        assert response.status_code == 404


class TestRemoveFriend:
    """Tests for DELETE /v1/friends/{friend_id}."""

    def test_remove_friend_success(self, client, mock_async_db, mock_user):
        """Test removing a friend."""
        friend_id = "friend-id"
        friendship = MockFriendship(
            user_id=str(mock_user.id),
            friend_id=friend_id,
        )
        mock_async_db.db.execute.return_value = MockExecuteResult([friendship])

        response = client.delete(f"/v1/friends/{friend_id}")
        assert response.status_code == 200

    def test_remove_friend_not_found(self, client, mock_async_db, mock_user):
        """Test removing a non-friend."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])

        response = client.delete("/v1/friends/nonexistent")
        assert response.status_code == 404
