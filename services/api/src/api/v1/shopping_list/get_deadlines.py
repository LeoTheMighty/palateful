"""Get shopping list deadlines and urgency groupings endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User

from .utils.deadline import (
    DUE_REASONS,
    format_time_until,
    get_urgency_level,
)


class GetShoppingListDeadlines(AsyncEndpoint):
    """Get shopping list items grouped by deadline urgency."""

    async def execute(self, list_id: str):
        """
        Get shopping list items organized by deadline urgency.

        Returns items grouped into:
        - overdue: Past due items
        - urgent: Due within 2 hours
        - today: Due today
        - soon: Due within 3 days
        - normal: Due later
        - none: No deadline

        Also includes the next upcoming meal event info.

        Args:
            list_id: The shopping list's ID

        Returns:
            Items grouped by urgency with countdown info
        """
        user: User = self.user
        now = datetime.now()

        shopping_list_result = await self.db.execute(
            select(ShoppingList)
            .options(
                selectinload(ShoppingList.items).selectinload(
                    ShoppingListItem.meal_event
                )
            )
            .where(ShoppingList.id == list_id)
        )
        shopping_list = shopping_list_result.scalars().first()
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

        items_by_urgency: dict[str, list] = {
            "overdue": [],
            "urgent": [],
            "today": [],
            "soon": [],
            "normal": [],
            "none": [],
        }

        next_deadline = None
        next_meal_event = None
        unchecked_count = 0
        checked_count = 0

        for item in shopping_list.items:
            if item.archived_at is not None:
                continue

            if item.is_checked:
                checked_count += 1
                continue  # Skip checked items from urgency grouping

            unchecked_count += 1

            urgency = get_urgency_level(item.due_at, now)

            item_data = GetShoppingListDeadlines.ItemResponse(
                id=str(item.id),
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                category=item.category,
                due_at=item.due_at,
                due_reason=item.due_reason,
                due_reason_text=DUE_REASONS.get(item.due_reason) if item.due_reason else None,
                time_until=format_time_until(item.due_at, now) if item.due_at else None,
                urgency=urgency,
                priority=item.priority,
                meal_event_id=str(item.meal_event_id) if item.meal_event_id else None,
                assigned_to_user_id=(
                    str(item.assigned_to_user_id) if item.assigned_to_user_id else None
                ),
                notes=item.notes,
            )

            items_by_urgency[urgency].append(item_data)

            if item.due_at and (next_deadline is None or item.due_at < next_deadline):
                next_deadline = item.due_at

            if item.meal_event and (
                next_meal_event is None
                or item.meal_event.scheduled_at < next_meal_event["scheduled_at"]
            ):
                event = item.meal_event
                prep_start = event.scheduled_at
                if event.prep_start_offset_minutes:  # pragma: no cover — meal event prep offset
                    prep_start = event.scheduled_at - __import__("datetime").timedelta(
                        minutes=event.prep_start_offset_minutes
                    )
                next_meal_event = {
                    "id": str(event.id),
                    "title": event.title,
                    "scheduled_at": event.scheduled_at,
                    "prep_start_at": prep_start,
                    "time_until_prep": format_time_until(prep_start, now),
                }

        for urgency_group in items_by_urgency.values():
            urgency_group.sort(
                key=lambda x: (
                    x.due_at if x.due_at else datetime.max.replace(tzinfo=None),
                    x.priority,
                )
            )

        next_meal_response = None
        if next_meal_event:
            next_meal_response = GetShoppingListDeadlines.MealEventInfo(
                id=next_meal_event["id"],
                title=next_meal_event["title"],
                scheduled_at=next_meal_event["scheduled_at"],
                prep_start_at=next_meal_event["prep_start_at"],
                time_until_prep=next_meal_event["time_until_prep"],
            )

        return success(
            data=GetShoppingListDeadlines.Response(
                next_deadline=next_deadline,
                next_meal_event=next_meal_response,
                unchecked_count=unchecked_count,
                checked_count=checked_count,
                items_by_urgency=GetShoppingListDeadlines.ItemsByUrgency(
                    overdue=items_by_urgency["overdue"],
                    urgent=items_by_urgency["urgent"],
                    today=items_by_urgency["today"],
                    soon=items_by_urgency["soon"],
                    normal=items_by_urgency["normal"],
                    none=items_by_urgency["none"],
                ),
            )
        )

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        category: str | None = None
        due_at: datetime | None = None
        due_reason: str | None = None
        due_reason_text: str | None = None
        time_until: str | None = None
        urgency: str
        priority: int = 3
        meal_event_id: str | None = None
        assigned_to_user_id: str | None = None
        notes: str | None = None

    class MealEventInfo(BaseModel):
        id: str
        title: str
        scheduled_at: datetime
        prep_start_at: datetime
        time_until_prep: str

    class ItemsByUrgency(BaseModel):
        overdue: list["GetShoppingListDeadlines.ItemResponse"]
        urgent: list["GetShoppingListDeadlines.ItemResponse"]
        today: list["GetShoppingListDeadlines.ItemResponse"]
        soon: list["GetShoppingListDeadlines.ItemResponse"]
        normal: list["GetShoppingListDeadlines.ItemResponse"]
        none: list["GetShoppingListDeadlines.ItemResponse"]

    class Response(BaseModel):
        next_deadline: datetime | None = None
        next_meal_event: "GetShoppingListDeadlines.MealEventInfo | None" = None
        unchecked_count: int
        checked_count: int
        items_by_urgency: "GetShoppingListDeadlines.ItemsByUrgency"
