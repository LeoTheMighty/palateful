"""Update shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User

VALID_STATUSES = ["pending", "in_progress", "completed"]
VALID_SORT_BY = ["deadline", "category", "name", "checked", "added_at"]


class UpdateShoppingList(AsyncEndpoint):
    """Update a shopping list."""

    async def execute(self, list_id: str, params: "UpdateShoppingList.Params"):
        """
        Update a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Update parameters

        Returns:
            Updated shopping list data
        """
        user: User = self.user

        shopping_list_result = await self.db.execute(
            select(ShoppingList)
            .options(
                selectinload(ShoppingList.items),
                selectinload(ShoppingList.members),
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
        can_edit = is_owner or (
            membership
            and membership.role in ("owner", "editor")
            and not membership.archived_at
        )

        if not can_edit:
            raise APIException(
                status_code=403,
                detail="You don't have permission to update this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        if params.status and params.status not in VALID_STATUSES:
            raise APIException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
                code=ErrorCode.INVALID_REQUEST,
            )

        if params.sort_by and params.sort_by not in VALID_SORT_BY:
            raise APIException(
                status_code=400,
                detail=f"Invalid sort_by. Must be one of: {', '.join(VALID_SORT_BY)}",
                code=ErrorCode.INVALID_REQUEST,
            )

        if params.name is not None:
            shopping_list.name = params.name
        if params.status is not None:
            # Auto-recovery: if completing the default list, restore previous
            if params.status == "completed" and str(shopping_list.id) == str(user.default_shopping_list_id or ""):
                user.default_shopping_list_id = user.previous_shopping_list_id
                user.previous_shopping_list_id = None
            shopping_list.status = params.status

        if params.default_deadline is not None:
            shopping_list.default_deadline = params.default_deadline
        if params.auto_populate_from_calendar is not None:
            shopping_list.auto_populate_from_calendar = params.auto_populate_from_calendar
        if params.calendar_lookahead_days is not None:
            shopping_list.calendar_lookahead_days = params.calendar_lookahead_days
        if params.widget_color is not None:
            shopping_list.widget_color = params.widget_color
        if params.sort_by is not None:
            shopping_list.sort_by = params.sort_by

        await self.database.db.commit()
        await self.database.db.refresh(shopping_list)

        items = []
        for item in shopping_list.items:
            if item.archived_at is None:
                items.append(
                    UpdateShoppingList.ItemResponse(
                        id=str(item.id),
                        name=item.name,
                        quantity=item.quantity,
                        unit=item.unit,
                        is_checked=item.is_checked,
                        category=item.category,
                        due_at=item.due_at,
                        priority=item.priority,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                )

        member_count = 0
        if shopping_list.is_shared:
            member_count = len(
                [m for m in shopping_list.members if m.archived_at is None]
            )

        restored_default_id = str(user.default_shopping_list_id) if user.default_shopping_list_id else None

        return success(
            data=UpdateShoppingList.Response(
                id=str(shopping_list.id),
                name=shopping_list.name,
                status=shopping_list.status,
                meal_event_id=(
                    str(shopping_list.meal_event_id)
                    if shopping_list.meal_event_id
                    else None
                ),
                pantry_id=(
                    str(shopping_list.pantry_id) if shopping_list.pantry_id else None
                ),
                owner_id=str(shopping_list.owner_id),
                is_shared=shopping_list.is_shared,
                share_code=shopping_list.share_code,
                default_deadline=shopping_list.default_deadline,
                auto_populate_from_calendar=shopping_list.auto_populate_from_calendar,
                calendar_lookahead_days=shopping_list.calendar_lookahead_days,
                widget_color=shopping_list.widget_color,
                sort_by=shopping_list.sort_by,
                member_count=member_count,
                restored_default_shopping_list_id=restored_default_id,
                items=items,
                created_at=shopping_list.created_at,
                updated_at=shopping_list.updated_at,
            )
        )

    class Params(BaseModel):
        name: str | None = None
        status: str | None = None
        default_deadline: datetime | None = None
        auto_populate_from_calendar: bool | None = None
        calendar_lookahead_days: int | None = None
        widget_color: str | None = None
        sort_by: str | None = None

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        category: str | None = None
        due_at: datetime | None = None
        priority: int = 3
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        id: str
        name: str | None = None
        status: str
        meal_event_id: str | None = None
        pantry_id: str | None = None
        owner_id: str
        is_shared: bool = False
        share_code: str | None = None
        default_deadline: datetime | None = None
        auto_populate_from_calendar: bool = True
        calendar_lookahead_days: int = 7
        widget_color: str | None = None
        sort_by: str = "deadline"
        member_count: int = 0
        restored_default_shopping_list_id: str | None = None
        items: list["UpdateShoppingList.ItemResponse"] = []
        created_at: datetime
        updated_at: datetime
