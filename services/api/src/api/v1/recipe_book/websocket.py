"""WebSocket handler for recipe book real-time sync."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class RecipeBookConnectionManager:
    """Manages WebSocket connections for recipe book real-time sync."""

    def __init__(self):
        # Map of recipe_book_id -> set of (user_id, websocket)
        self.active_connections: dict[str, set[tuple[str, WebSocket]]] = {}
        # Map of websocket -> (user_id, set of recipe_book_ids)
        self.connection_info: dict[WebSocket, tuple[str, set[str]]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user: User,
        book_id: str,
    ) -> bool:
        """
        Connect a user to a recipe book room.

        Returns:
            True if connection successful, False otherwise
        """
        await websocket.accept()

        user_id = str(user.id)

        if websocket not in self.connection_info:
            self.connection_info[websocket] = (user_id, set())

        if book_id not in self.active_connections:
            self.active_connections[book_id] = set()

        self.active_connections[book_id].add((user_id, websocket))
        self.connection_info[websocket][1].add(book_id)

        return True

    def disconnect(self, websocket: WebSocket):
        """Disconnect a websocket from all rooms."""
        if websocket not in self.connection_info:
            return

        user_id, book_ids = self.connection_info[websocket]

        for book_id in book_ids:
            if book_id in self.active_connections:
                self.active_connections[book_id].discard((user_id, websocket))
                if not self.active_connections[book_id]:
                    del self.active_connections[book_id]

        del self.connection_info[websocket]

    async def broadcast_to_book(
        self,
        book_id: str,
        message: dict[str, Any],
        exclude_websocket: WebSocket | None = None,
    ):
        """Broadcast a message to all connections in a recipe book room."""
        if book_id not in self.active_connections:
            return

        message_json = json.dumps(message, default=str)
        disconnected = []

        # Snapshot to list to avoid RuntimeError if connections change during awaits
        connections = list(self.active_connections.get(book_id, set()))
        for _user_id, websocket in connections:
            if websocket == exclude_websocket:
                continue
            try:
                await websocket.send_text(message_json)
            except Exception:
                disconnected.append(websocket)

        for ws in disconnected:
            self.disconnect(ws)

    def get_online_users(self, book_id: str) -> list[str]:
        """Get list of online user IDs for a recipe book."""
        if book_id not in self.active_connections:
            return []

        return list(set(user_id for user_id, _ in self.active_connections[book_id]))


# Global connection manager instance
manager = RecipeBookConnectionManager()


async def recipe_book_websocket_handler(
    websocket: WebSocket,
    book_id: str,
    user: User,
    db,
):
    """
    Handle WebSocket connection for a recipe book.

    Message types from client:
    - ping: {"type": "ping"}

    Message types to client:
    - connected: Initial confirmation with online users
    - recipe_added: A recipe was added to this book
    - recipe_updated: A recipe in this book was updated
    - recipe_removed: A recipe in this book was archived/deleted
    - pong: Response to ping
    """

    # Verify access to the recipe book via membership
    membership = (
        db.query(RecipeBookUser)
        .filter(RecipeBookUser.recipe_book_id == book_id)
        .filter(RecipeBookUser.user_id == user.id)
        .first()
    )

    if not membership:
        await websocket.close(code=4003, reason="Access denied")
        return

    await manager.connect(websocket, user, book_id)

    online_users = manager.get_online_users(book_id)
    await websocket.send_json({
        "type": "connected",
        "recipe_book_id": book_id,
        "online_users": online_users,
        "timestamp": datetime.now(UTC).isoformat(),
    })

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


async def broadcast_event_to_recipe_book(
    book_id: str | uuid.UUID,
    event_type: str,
    event_data: dict[str, Any],
    user_id: str | uuid.UUID | None = None,
):
    """
    Broadcast a recipe mutation event to all connected clients for a recipe book.

    Call this after any recipe create/update/delete/fork operation to notify
    all connected clients in real-time.

    Args:
        book_id: The recipe book ID whose clients should be notified
        event_type: "recipe_added", "recipe_updated", or "recipe_removed"
        event_data: Minimal payload (e.g. {"recipe_id": "...", "name": "..."})
        user_id: The user who triggered the event (optional, for attribution)
    """
    await manager.broadcast_to_book(
        str(book_id),
        {
            "type": event_type,
            "recipe_book_id": str(book_id),
            "data": event_data,
            "user_id": str(user_id) if user_id else None,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
