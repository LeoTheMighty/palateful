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


# ---------------------------------------------------------------------------
# AddNoteToRecipeTool
# ---------------------------------------------------------------------------


class TestAddNoteToRecipeTool:
    """Tests for AddNoteToRecipeTool."""

    def _make_recipe(self, book_id=None):
        recipe = MagicMock()
        recipe.id = uuid.uuid4()
        recipe.name = "Chicken Pasta"
        recipe.recipe_book_id = book_id or uuid.uuid4()
        return recipe

    def _make_membership(self):
        return MagicMock()

    def test_add_note_creates_note_with_recipe_id(self):
        """Note is created on the recipe identified by recipe_id."""
        from agent.tools.recipes import AddNoteToRecipeTool

        tool = AddNoteToRecipeTool()
        recipe = self._make_recipe()
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        # db.get returns the recipe; execute().scalar_one_or_none returns membership
        mock_db.get.return_value = recipe
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: self._make_membership())

        # note.id is set after flush — simulate via MagicMock auto-attribute
        result = tool.execute(db=mock_db, user_id=user_id, note_body="Try more garlic", recipe_id=str(recipe.id))

        assert result.success is True
        assert result.data["recipe_name"] == "Chicken Pasta"
        assert result.data["note_body"] == "Try more garlic"
        assert result.data["recipe_id"] == str(recipe.id)
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_add_note_by_recipe_name_uses_search(self):
        """When recipe_name is provided (no recipe_id), semantic search resolves the recipe."""
        from agent.tools.recipes import AddNoteToRecipeTool

        tool = AddNoteToRecipeTool()
        book_id = uuid.uuid4()
        recipe = self._make_recipe(book_id=book_id)
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        # First execute call returns book_ids, second returns recipe row, third returns membership
        mock_db.execute.side_effect = [
            MagicMock(fetchall=lambda: [(book_id,)]),           # book_ids query
            MagicMock(fetchone=lambda: (recipe, 0.1)),          # recipe search
            MagicMock(scalar_one_or_none=lambda: self._make_membership()),  # membership check
        ]

        with patch("sentence_transformers.SentenceTransformer") as mock_st:
            mock_st.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)
            result = tool.execute(db=mock_db, user_id=user_id, note_body="Less salt", recipe_name="chicken pasta")

        assert result.success is True
        assert result.data["recipe_name"] == "Chicken Pasta"
        assert result.data["note_body"] == "Less salt"

    def test_add_note_returns_error_for_inaccessible_recipe(self):
        """Returns failure when user is not a member of the recipe's book."""
        from agent.tools.recipes import AddNoteToRecipeTool

        tool = AddNoteToRecipeTool()
        recipe = self._make_recipe()
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        mock_db.get.return_value = recipe
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)  # no membership

        result = tool.execute(db=mock_db, user_id=user_id, note_body="Test note", recipe_id=str(recipe.id))

        assert result.success is False
        assert "access denied" in result.error.lower() or "not found" in result.error.lower()
        mock_db.add.assert_not_called()

    def test_add_note_returns_error_for_missing_recipe(self):
        """Returns failure when recipe_id does not match any recipe."""
        from agent.tools.recipes import AddNoteToRecipeTool

        tool = AddNoteToRecipeTool()
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        mock_db.get.return_value = None  # recipe not found

        result = tool.execute(db=mock_db, user_id=user_id, note_body="Test note", recipe_id=str(uuid.uuid4()))

        assert result.success is False
        assert "not found" in result.error.lower()
        mock_db.add.assert_not_called()

    def test_add_note_returns_error_for_empty_body(self):
        """Returns failure when note_body is blank."""
        from agent.tools.recipes import AddNoteToRecipeTool

        tool = AddNoteToRecipeTool()
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        result = tool.execute(db=mock_db, user_id=user_id, note_body="   ", recipe_id=str(uuid.uuid4()))

        assert result.success is False
        assert "empty" in result.error.lower()
        mock_db.add.assert_not_called()

    def test_add_note_returns_error_when_no_recipe_identifier(self):
        """Returns failure when neither recipe_id nor recipe_name is provided."""
        from agent.tools.recipes import AddNoteToRecipeTool

        tool = AddNoteToRecipeTool()
        mock_db = MagicMock()

        result = tool.execute(db=mock_db, user_id=str(uuid.uuid4()), note_body="Some note")

        assert result.success is False
        assert "required" in result.error.lower()

    def test_add_note_returns_error_for_whitespace_recipe_name(self):
        """Returns failure when recipe_name is whitespace only."""
        from agent.tools.recipes import AddNoteToRecipeTool

        tool = AddNoteToRecipeTool()
        mock_db = MagicMock()

        result = tool.execute(db=mock_db, user_id=str(uuid.uuid4()), note_body="Some note", recipe_name="   ")

        assert result.success is False
        assert "required" in result.error.lower()
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# SuggestRecipeTool
# ---------------------------------------------------------------------------


class TestSuggestRecipeTool:
    """Tests for SuggestRecipeTool."""

    def test_suggest_recipe_tool_name(self):
        """SuggestRecipeTool has correct tool name."""
        from agent.tools.recipes import SuggestRecipeTool

        tool = SuggestRecipeTool()
        assert tool.name == "suggest_recipe"

    def test_suggest_recipe_tool_parameters_shape(self):
        """SuggestRecipeTool parameters include required ingredients field."""
        from agent.tools.recipes import SuggestRecipeTool

        tool = SuggestRecipeTool()
        params = tool.parameters
        assert "ingredients" in params["properties"]
        assert "ingredients" in params.get("required", [])
        assert "cuisine" in params["properties"]
        assert "meal_type" in params["properties"]

    def test_suggest_recipe_in_tools_registry(self):
        """SuggestRecipeTool is registered in the agent library TOOLS dict."""
        from agent.tools import TOOLS
        assert "suggest_recipe" in TOOLS

    def test_suggest_recipe_executes_with_mocked_llm_provider(self):
        """SuggestRecipeTool calls LLM provider and returns structured suggestion."""
        from agent.tools.recipes import SuggestRecipeTool

        tool = SuggestRecipeTool()
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        mock_response = MagicMock()
        mock_response.content = "Chicken stir-fry: Heat oil in a wok, add garlic..."
        mock_response.model = "gpt-4o-mini"

        mock_provider = MagicMock()
        mock_provider.chat.return_value = mock_response

        with patch("agent.llm.get_llm_provider", return_value=mock_provider):
            result = tool.execute(db=mock_db, user_id=user_id, ingredients=["chicken", "garlic"])

        assert result.success is True
        assert result.data["suggestion"] == "Chicken stir-fry: Heat oil in a wok, add garlic..."
        assert result.data["based_on_ingredients"] == ["chicken", "garlic"]
        assert result.data["model_used"] == "gpt-4o-mini"
        mock_provider.chat.assert_called_once()


# ---------------------------------------------------------------------------
# Recipe context support (Story 11.5)
# ---------------------------------------------------------------------------


class TestRecipeContext:
    """Tests for recipe_context in SendMessageParams."""

    def test_send_message_params_accepts_recipe_context(self):
        """SendMessageParams accepts optional recipe_context field."""
        from api.v1.chat.send_message import SendMessageParams

        params = SendMessageParams(
            message="Can I substitute butter?",
            recipe_context="Recipe: Pasta\nIngredients:\n- olive oil",
        )
        assert params.message == "Can I substitute butter?"
        assert params.recipe_context == "Recipe: Pasta\nIngredients:\n- olive oil"

    def test_send_message_params_works_without_recipe_context(self):
        """SendMessageParams works without recipe_context (backward compatible)."""
        from api.v1.chat.send_message import SendMessageParams

        params = SendMessageParams(message="Hello AI")
        assert params.message == "Hello AI"
        assert params.recipe_context is None

    def test_send_message_params_rejects_oversized_recipe_context(self):
        """SendMessageParams rejects recipe_context exceeding max_length."""
        import pytest

        from api.v1.chat.send_message import SendMessageParams

        with pytest.raises(Exception):
            SendMessageParams(message="test", recipe_context="x" * 5001)
