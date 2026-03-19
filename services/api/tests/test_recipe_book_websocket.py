"""Tests for recipe book WebSocket connection manager and broadcast."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test RecipeBookConnectionManager
# ---------------------------------------------------------------------------

class TestRecipeBookConnectionManager:
    """Tests for RecipeBookConnectionManager in-memory state."""

    @pytest.fixture
    def manager(self):
        """Fresh manager instance per test."""
        from api.v1.recipe_book.websocket import RecipeBookConnectionManager
        return RecipeBookConnectionManager()

    @pytest.fixture
    def mock_user(self):
        """A simple mock user."""
        user = MagicMock()
        user.id = uuid.UUID("a0000000-0000-0000-0000-000000000001")
        user.name = "Alice"
        return user

    @pytest.fixture
    def mock_websocket(self):
        """A mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    def test_connect_adds_connection_to_room(self, manager, mock_user, mock_websocket):
        """Connecting adds the (user_id, ws) pair to the room."""
        book_id = "book-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_websocket, mock_user, book_id)
        )
        assert book_id in manager.active_connections
        assert (str(mock_user.id), mock_websocket) in manager.active_connections[book_id]

    def test_disconnect_removes_connection(self, manager, mock_user, mock_websocket):
        """Disconnecting removes the websocket from all rooms."""
        book_id = "book-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_websocket, mock_user, book_id)
        )
        manager.disconnect(mock_websocket)
        assert book_id not in manager.active_connections

    def test_disconnect_removes_empty_room(self, manager, mock_user, mock_websocket):
        """Room entry is deleted when the last connection leaves."""
        book_id = "book-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_websocket, mock_user, book_id)
        )
        manager.disconnect(mock_websocket)
        assert book_id not in manager.active_connections

    def test_disconnect_noop_for_unknown_websocket(self, manager):
        """Disconnecting an unknown websocket does not raise."""
        ws = AsyncMock()
        manager.disconnect(ws)  # Should not raise

    def test_get_online_users_returns_ids(self, manager, mock_user, mock_websocket):
        """get_online_users returns user IDs for connected clients."""
        book_id = "book-1"
        asyncio.get_event_loop().run_until_complete(
            manager.connect(mock_websocket, mock_user, book_id)
        )
        online = manager.get_online_users(book_id)
        assert str(mock_user.id) in online

    def test_get_online_users_empty_for_unknown_book(self, manager):
        """get_online_users returns empty list for book with no connections."""
        online = manager.get_online_users("nonexistent-book")
        assert online == []

    def test_broadcast_sends_to_all_connections(self, manager, mock_user):
        """Broadcast sends JSON to all connected WebSockets."""
        book_id = "book-1"
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        for ws in (ws1, ws2):
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()

        user2 = MagicMock()
        user2.id = uuid.UUID("a0000000-0000-0000-0000-000000000002")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(manager.connect(ws1, mock_user, book_id))
        loop.run_until_complete(manager.connect(ws2, user2, book_id))

        msg = {"type": "recipe_added", "recipe_book_id": book_id, "data": {}}
        loop.run_until_complete(manager.broadcast_to_book(book_id, msg))

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        # Verify message content
        sent = json.loads(ws1.send_text.call_args[0][0])
        assert sent["type"] == "recipe_added"

    def test_broadcast_excludes_sender(self, manager, mock_user):
        """Broadcast with exclude_websocket skips that connection."""
        book_id = "book-1"
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        user2 = MagicMock()
        user2.id = uuid.UUID("a0000000-0000-0000-0000-000000000003")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(manager.connect(ws1, mock_user, book_id))
        loop.run_until_complete(manager.connect(ws2, user2, book_id))

        msg = {"type": "recipe_updated", "data": {}}
        loop.run_until_complete(manager.broadcast_to_book(book_id, msg, exclude_websocket=ws1))

        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_once()

    def test_broadcast_to_empty_book_no_error(self, manager):
        """Broadcasting to a book with no connections does not raise."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            manager.broadcast_to_book("empty-book", {"type": "recipe_added"})
        )  # Should not raise


# ---------------------------------------------------------------------------
# Test broadcast_event_to_recipe_book helper
# ---------------------------------------------------------------------------

class TestBroadcastEventToRecipeBook:
    """Tests for the broadcast_event_to_recipe_book module-level function."""

    def test_broadcast_calls_manager(self):
        """broadcast_event_to_recipe_book delegates to the manager."""
        from api.v1.recipe_book import websocket as ws_module

        mock_manager = AsyncMock()
        mock_manager.broadcast_to_book = AsyncMock()

        with patch.object(ws_module, "manager", mock_manager):
            book_id = str(uuid.uuid4())
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                ws_module.broadcast_event_to_recipe_book(
                    book_id, "recipe_removed", {"recipe_id": "r-1"}
                )
            )

        mock_manager.broadcast_to_book.assert_called_once()
        call_args = mock_manager.broadcast_to_book.call_args
        assert call_args[0][0] == book_id
        msg = call_args[0][1]
        assert msg["type"] == "recipe_removed"
        assert msg["data"] == {"recipe_id": "r-1"}
        assert msg["recipe_book_id"] == book_id


# ---------------------------------------------------------------------------
# Test WebSocket handler access control
# ---------------------------------------------------------------------------

class TestRecipeBookWebSocketHandler:
    """Tests for the recipe_book_websocket_handler access control."""

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = uuid.UUID("a0000000-0000-0000-0000-000000000001")
        user.name = "Alice"
        return user

    def test_handler_rejects_non_member(self, mock_user):
        """Handler closes WebSocket with 4003 if user has no membership."""
        from api.v1.recipe_book.websocket import recipe_book_websocket_handler

        websocket = AsyncMock()
        websocket.close = AsyncMock()
        websocket.send_json = AsyncMock()

        db = MagicMock()
        # query().filter().filter().first() returns None (no membership)
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        book_id = str(uuid.uuid4())
        asyncio.get_event_loop().run_until_complete(
            recipe_book_websocket_handler(websocket, book_id, mock_user, db)
        )

        websocket.close.assert_called_once_with(code=4003, reason="Access denied")

    def test_handler_sends_connected_message_on_success(self, mock_user):
        """Handler sends a 'connected' message after access is granted."""
        from api.v1.recipe_book.websocket import (
            RecipeBookConnectionManager,
            recipe_book_websocket_handler,
        )

        websocket = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.send_json = AsyncMock()
        # Simulate WebSocketDisconnect after the initial send
        from fastapi import WebSocketDisconnect
        websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        db = MagicMock()
        mock_membership = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_membership

        book_id = str(uuid.uuid4())

        # Use a fresh manager to avoid cross-test state
        fresh_manager = RecipeBookConnectionManager()
        from api.v1.recipe_book import websocket as ws_module
        with patch.object(ws_module, "manager", fresh_manager):
            asyncio.get_event_loop().run_until_complete(
                recipe_book_websocket_handler(websocket, book_id, mock_user, db)
            )

        # Should have called send_json with the "connected" message
        websocket.send_json.assert_called_once()
        msg = websocket.send_json.call_args[0][0]
        assert msg["type"] == "connected"
        assert msg["recipe_book_id"] == book_id
