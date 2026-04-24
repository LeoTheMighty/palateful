"""Get shopping list events for sync endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_event import ShoppingListEvent
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class GetShoppingListEvents(AsyncEndpoint):
    """Get shopping list events for sync/catch-up."""

    async def execute(
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

        shopping_list = await self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        is_owner = shopping_list.owner_id == user.id
        membership = await self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=user.id
        )
        if not is_owner and not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Inline event replay query — ShoppingListEventService stays sync
        # for the WebSocket handler; here we run the two reads directly on
        # the AsyncSession to avoid building a parallel async service.
        events_result = await self.db.execute(
            select(ShoppingListEvent)
            .options(selectinload(ShoppingListEvent.user))
            .where(ShoppingListEvent.shopping_list_id == shopping_list.id)
            .where(ShoppingListEvent.sequence > since_sequence)
            .order_by(ShoppingListEvent.sequence)
            .limit(min(limit, 500))
        )
        events = list(events_result.scalars().all())

        current_sequence_result = await self.db.execute(
            select(func.max(ShoppingListEvent.sequence)).where(
                ShoppingListEvent.shopping_list_id == shopping_list.id
            )
        )
        current_sequence = current_sequence_result.scalar() or 0

        if membership:
            membership.last_seen_at = datetime.utcnow()
            await self.database.db.commit()

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
