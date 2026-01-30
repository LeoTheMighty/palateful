"""Get shopping list events for sync endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User

from .utils.events import ShoppingListEventService


class GetShoppingListEvents(Endpoint):
    """Get shopping list events for sync/catch-up."""

    def execute(
        self,
        list_id: str,
        since_sequence: int = 0,
        limit: int = 100,
    ):
        """
        Get shopping list events since a specific sequence number.

        This endpoint is used for:
        1. Initial sync when connecting
        2. Catching up after a disconnect
        3. Polling fallback when WebSocket isn't available

        Args:
            list_id: The shopping list's ID
            since_sequence: Get events after this sequence (0 = all)
            limit: Maximum number of events to return

        Returns:
            List of events with current sequence number
        """
        user: User = self.user

        # Find shopping list
        shopping_list = self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        # Check access - owner or member
        is_owner = shopping_list.owner_id == user.id
        membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=user.id
        )
        if not is_owner and not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Get events
        event_service = ShoppingListEventService(self.db)
        events = event_service.get_events_since(
            shopping_list_id=shopping_list.id,
            since_sequence=since_sequence,
            limit=min(limit, 500),  # Cap at 500
        )
        current_sequence = event_service.get_current_sequence(shopping_list.id)

        # Update last_seen_at for the member
        if membership:
            membership.last_seen_at = datetime.utcnow()
            self.database.db.commit()

        # Build response
        event_responses = []
        for event in events:
            event_user = event.user
            event_responses.append(
                GetShoppingListEvents.EventResponse(
                    id=str(event.id),
                    event_type=event.event_type,
                    event_data=event.event_data,
                    user_id=str(event.user_id) if event.user_id else None,
                    user_name=event_user.name if event_user else None,
                    sequence=event.sequence,
                    created_at=event.created_at,
                )
            )

        return success(
            data=GetShoppingListEvents.Response(
                events=event_responses,
                current_sequence=current_sequence,
                has_more=len(events) >= limit,
            )
        )

    class EventResponse(BaseModel):
        id: str
        event_type: str
        event_data: dict
        user_id: str | None = None
        user_name: str | None = None
        sequence: int
        created_at: datetime

    class Response(BaseModel):
        events: list["GetShoppingListEvents.EventResponse"]
        current_sequence: int
        has_more: bool
