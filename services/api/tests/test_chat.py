"""Tests for AI chat endpoints."""

import os
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add agent library to path so SearchRecipesTool can be imported.
# The agent library transitively imports 'anthropic' and 'openai' which are not
# installed in the api test venv — stub them out before importing.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "libraries", "agent"),
)
_stub_mods = (
    "anthropic",
    "openai",
    "sentence_transformers",
    "langgraph",
    "langgraph.graph",
    "langchain_core",
    "langchain_core.tools",
)
for _mod in _stub_mods:
    sys.modules.setdefault(_mod, MagicMock())

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


# ---------------------------------------------------------------------------
# SearchRecipesTool
# ---------------------------------------------------------------------------


class TestSearchRecipesTool:
    """Tests for SearchRecipesTool."""

    def test_search_recipes_includes_recipe_book_name(self):
        """Test that recipe_book_name is included in search results."""
        from unittest.mock import MagicMock, patch

        from agent.tools.recipes import SearchRecipesTool

        tool = SearchRecipesTool()

        # Build mock recipe with recipe_book relationship
        mock_book = MagicMock()
        mock_book.name = "Family Favourites"

        mock_recipe = MagicMock()
        mock_recipe.id = uuid.uuid4()
        mock_recipe.name = "Chicken Pasta"
        mock_recipe.recipe_book = mock_book
        mock_recipe.description = "A delicious pasta dish"
        mock_recipe.prep_time = 10
        mock_recipe.cook_time = 20
        mock_recipe.servings = 4
        mock_recipe.image_url = None
        mock_recipe.ingredients = []

        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        # Mock RecipeBookUser query returning one book_id
        book_id = uuid.uuid4()
        mock_db.execute.side_effect = [
            MagicMock(fetchall=lambda: [(book_id,)]),  # book_ids query
            MagicMock(fetchall=lambda: [(mock_recipe, 0.1)]),  # recipe search
        ]

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_st.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

            result = tool.execute(db=mock_db, user_id=user_id, query="pasta")

        assert result.success is True
        assert len(result.data["recipes"]) == 1
        recipe = result.data["recipes"][0]
        assert recipe["recipe_book_name"] == "Family Favourites"
        assert recipe["name"] == "Chicken Pasta"

    def test_search_recipes_empty_for_user_with_no_books(self):
        """Test that search returns empty list when user has no recipe books."""
        from agent.tools.recipes import SearchRecipesTool

        tool = SearchRecipesTool()
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        mock_db.execute.return_value = MagicMock(fetchall=lambda: [])

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_st.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

            result = tool.execute(db=mock_db, user_id=user_id, query="pasta")

        assert result.success is True
        assert result.data["recipes"] == []
        assert "no recipe books" in result.data["message"].lower()
