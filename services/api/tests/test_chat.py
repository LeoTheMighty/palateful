"""Tests for AI chat endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import MockModel, MockUser


class MockThread(MockModel):
    """Mock Thread model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "title": None,
            "chats": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockChat(MockModel):
    """Mock Chat model."""

    def __init__(self, **kwargs):
        defaults = {
            "thread_id": str(uuid.uuid4()),
            "role": "user",
            "content": "Hello",
            "tool_calls": None,
            "tool_call_id": None,
            "tool_name": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "model": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


# ---------------------------------------------------------------------------
# CreateThread
# ---------------------------------------------------------------------------

class TestCreateThread:
    """Tests for POST /v1/chat/threads."""

    def test_create_thread_no_title(self, client, mock_db, mock_user):
        """Test creating a thread with no title."""
        response = client.post("/v1/chat/threads", json={})
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["title"] is None
        assert data["message_count"] == 0

    def test_create_thread_with_title(self, client, mock_db, mock_user):
        """Test creating a thread with a title."""
        response = client.post("/v1/chat/threads", json={"title": "My Pasta Quest"})
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Pasta Quest"


# ---------------------------------------------------------------------------
# ListThreads
# ---------------------------------------------------------------------------

class TestListThreads:
    """Tests for GET /v1/chat/threads."""

    def test_list_threads_empty(self, client, mock_db, mock_user):
        """Test listing threads when user has none."""
        from utils.models.thread import Thread

        mock_db.db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(all=lambda: [])
        )
        response = client.get("/v1/chat/threads")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_threads_with_results(self, client, mock_db, mock_user):
        """Test listing threads returns thread summaries."""
        thread = MockThread(
            user_id=str(mock_user.id),
            title="Dinner Ideas",
            chats=[MockChat(role="user", content="Find me pasta")],
        )
        mock_db.db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(all=lambda: [thread])
        )
        response = client.get("/v1/chat/threads")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Dinner Ideas"
        assert data["items"][0]["message_count"] == 1


# ---------------------------------------------------------------------------
# GetThread
# ---------------------------------------------------------------------------

class TestGetThread:
    """Tests for GET /v1/chat/threads/{thread_id}."""

    def test_get_thread_success(self, client, mock_db, mock_user):
        """Test getting a thread with messages."""
        thread_id = str(uuid.uuid4())
        chat = MockChat(role="user", content="Hello AI")
        thread = MockThread(id=thread_id, user_id=str(mock_user.id), chats=[chat])

        from utils.models.thread import Thread
        mock_db.set_find_by(Thread, thread)

        response = client.get(f"/v1/chat/threads/{thread_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == thread_id
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"

    def test_get_thread_not_found(self, client, mock_db, mock_user):
        """Test getting a non-existent thread returns 404."""
        from utils.models.thread import Thread
        mock_db.set_find_by(Thread, None)

        response = client.get(f"/v1/chat/threads/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_get_thread_wrong_user(self, client, mock_db, mock_user):
        """Test getting another user's thread returns 404."""
        thread = MockThread(user_id=str(uuid.uuid4()))  # different user

        from utils.models.thread import Thread
        mock_db.set_find_by(Thread, thread)

        response = client.get(f"/v1/chat/threads/{thread.id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DeleteThread
# ---------------------------------------------------------------------------

class TestDeleteThread:
    """Tests for DELETE /v1/chat/threads/{thread_id}."""

    def test_delete_thread_success(self, client, mock_db, mock_user):
        """Test deleting a thread sets archived_at."""
        thread_id = str(uuid.uuid4())
        thread = MockThread(id=thread_id, user_id=str(mock_user.id))

        from utils.models.thread import Thread
        mock_db.set_find_by(Thread, thread)

        response = client.delete(f"/v1/chat/threads/{thread_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert thread.archived_at is not None

    def test_delete_thread_not_found(self, client, mock_db, mock_user):
        """Test deleting a non-existent thread returns 404."""
        from utils.models.thread import Thread
        mock_db.set_find_by(Thread, None)

        response = client.delete(f"/v1/chat/threads/{uuid.uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Token cap enforcement
# ---------------------------------------------------------------------------

class TestTokenCap:
    """Tests for per-user monthly token cap."""

    def test_get_user_monthly_tokens_zero(self):
        """Test token count returns 0 when no chats exist."""
        from api.v1.chat.agent_loop import get_user_monthly_tokens

        db = MagicMock()
        db.execute.return_value = MagicMock(scalar=lambda: 0)
        result = get_user_monthly_tokens(db, uuid.uuid4())
        assert result == 0

    def test_get_user_monthly_tokens_sum(self):
        """Test token count sums tokens correctly."""
        from api.v1.chat.agent_loop import get_user_monthly_tokens

        db = MagicMock()
        db.execute.return_value = MagicMock(scalar=lambda: 1500)
        result = get_user_monthly_tokens(db, uuid.uuid4())
        assert result == 1500
