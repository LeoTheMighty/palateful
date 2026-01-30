"""WebSocket handler for shopping list real-time sync."""

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User

from .utils.events import ShoppingListEventService


class ConnectionManager:
    """Manages WebSocket connections for shopping list sync."""

    def __init__(self):
        # Map of shopping_list_id -> set of (user_id, websocket)
        self.active_connections: dict[str, set[tuple[str, WebSocket]]] = {}
        # Map of websocket -> (user_id, shopping_list_ids)
        self.connection_info: dict[WebSocket, tuple[str, set[str]]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user: User,
        shopping_list_id: str,
    ) -> bool:
        """
        Connect a user to a shopping list room.

        Returns:
            True if connection successful, False otherwise
        """
        await websocket.accept()

        user_id = str(user.id)

        # Initialize connection info if new websocket
        if websocket not in self.connection_info:
            self.connection_info[websocket] = (user_id, set())

        # Add to room
        if shopping_list_id not in self.active_connections:
            self.active_connections[shopping_list_id] = set()

        self.active_connections[shopping_list_id].add((user_id, websocket))
        self.connection_info[websocket][1].add(shopping_list_id)

        # Notify others in the room
        await self.broadcast_to_list(
            shopping_list_id,
            {
                "type": "presence_update",
                "user_id": user_id,
                "user_name": user.name,
                "status": "online",
                "timestamp": datetime.utcnow().isoformat(),
            },
            exclude_websocket=websocket,
        )

        return True

    def disconnect(self, websocket: WebSocket):
        """Disconnect a websocket from all rooms."""
        if websocket not in self.connection_info:
            return

        user_id, shopping_list_ids = self.connection_info[websocket]

        # Remove from all rooms
        for list_id in shopping_list_ids:
            if list_id in self.active_connections:
                self.active_connections[list_id].discard((user_id, websocket))
                if not self.active_connections[list_id]:
                    del self.active_connections[list_id]

        del self.connection_info[websocket]

    async def broadcast_to_list(
        self,
        shopping_list_id: str,
        message: dict[str, Any],
        exclude_websocket: WebSocket | None = None,
    ):
        """Broadcast a message to all connections in a shopping list room."""
        if shopping_list_id not in self.active_connections:
            return

        message_json = json.dumps(message, default=str)
        disconnected = []

        for _user_id, websocket in self.active_connections[shopping_list_id]:
            if websocket == exclude_websocket:
                continue
            try:
                await websocket.send_text(message_json)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(ws)

    def get_online_users(self, shopping_list_id: str) -> list[str]:
        """Get list of online user IDs for a shopping list."""
        if shopping_list_id not in self.active_connections:
            return []

        return list(set(user_id for user_id, _ in self.active_connections[shopping_list_id]))


# Global connection manager instance
manager = ConnectionManager()


async def shopping_list_websocket_handler(
    websocket: WebSocket,
    list_id: str,
    user: User,
    db: Session,
):
    """
    Handle WebSocket connection for a shopping list.

    Message types from client:
    - subscribe: Join a shopping list room
    - unsubscribe: Leave a shopping list room
    - presence: Update presence status (typing, shopping, etc.)
    - sync_request: Request full state sync

    Message types to client:
    - sync_response: Full state sync
    - item_added/updated/checked/removed: Item changes
    - member_joined/left: Membership changes
    - presence_update: User status changes
    - error: Error messages
    """
    # Verify access to the shopping list
    shopping_list = db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
    if not shopping_list:
        await websocket.close(code=4004, reason="Shopping list not found")
        return

    is_owner = shopping_list.owner_id == user.id
    membership = (
        db.query(ShoppingListUser)
        .filter(ShoppingListUser.shopping_list_id == list_id)
        .filter(ShoppingListUser.user_id == user.id)
        .first()
    )

    if not is_owner and not membership:
        await websocket.close(code=4003, reason="Access denied")
        return

    # Connect to the room
    await manager.connect(websocket, user, list_id)

    # Send initial sync
    event_service = ShoppingListEventService(db)
    current_sequence = event_service.get_current_sequence(shopping_list.id)
    online_users = manager.get_online_users(list_id)

    await websocket.send_json({
        "type": "sync_response",
        "shopping_list_id": list_id,
        "current_sequence": current_sequence,
        "online_users": online_users,
        "timestamp": datetime.utcnow().isoformat(),
    })

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")

            if message_type == "presence":
                # Broadcast presence update
                await manager.broadcast_to_list(
                    list_id,
                    {
                        "type": "presence_update",
                        "user_id": str(user.id),
                        "user_name": user.name,
                        "status": message.get("status", "online"),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            elif message_type == "sync_request":
                # Re-send current state
                since_sequence = message.get("since_sequence", 0)
                events = event_service.get_events_since(
                    shopping_list_id=shopping_list.id,
                    since_sequence=since_sequence,
                    limit=100,
                )

                await websocket.send_json({
                    "type": "sync_response",
                    "shopping_list_id": list_id,
                    "events": [
                        {
                            "id": str(e.id),
                            "event_type": e.event_type,
                            "event_data": e.event_data,
                            "user_id": str(e.user_id) if e.user_id else None,
                            "sequence": e.sequence,
                            "created_at": e.created_at.isoformat(),
                        }
                        for e in events
                    ],
                    "current_sequence": event_service.get_current_sequence(shopping_list.id),
                    "timestamp": datetime.utcnow().isoformat(),
                })

            elif message_type == "ping":
                # Respond to keepalive ping
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        # Clean up and notify others
        manager.disconnect(websocket)
        await manager.broadcast_to_list(
            list_id,
            {
                "type": "presence_update",
                "user_id": str(user.id),
                "user_name": user.name,
                "status": "offline",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


async def broadcast_event_to_list(
    shopping_list_id: str | uuid.UUID,
    event_type: str,
    event_data: dict[str, Any],
    user_id: str | uuid.UUID | None = None,
    sequence: int | None = None,
):
    """
    Broadcast an event to all connected clients for a shopping list.

    This should be called after creating a ShoppingListEvent to notify
    all connected clients in real-time.
    """
    list_id = str(shopping_list_id)
    await manager.broadcast_to_list(
        list_id,
        {
            "type": event_type,
            "shopping_list_id": list_id,
            "data": event_data,
            "user_id": str(user_id) if user_id else None,
            "sequence": sequence,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
