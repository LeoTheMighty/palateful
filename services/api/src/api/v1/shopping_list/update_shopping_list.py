"""Update shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User

VALID_STATUSES = ["pending", "in_progress", "completed"]
VALID_SORT_BY = ["deadline", "category", "name", "checked", "added_at"]


class UpdateShoppingList(Endpoint):
    """Update a shopping list."""

    def execute(self, list_id: str, params: "UpdateShoppingList.Params"):
        """
        Update a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Update parameters

        Returns:
            Updated shopping list data
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

        # Check access - owner or member with edit permission
        is_owner = shopping_list.owner_id == user.id
        membership = self.database.find_by(
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

        # Validate status if provided
        if params.status and params.status not in VALID_STATUSES:
            raise APIException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Validate sort_by if provided
        if params.sort_by and params.sort_by not in VALID_SORT_BY:
            raise APIException(
                status_code=400,
                detail=f"Invalid sort_by. Must be one of: {', '.join(VALID_SORT_BY)}",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Update basic fields
        if params.name is not None:
            shopping_list.name = params.name
        if params.status is not None:
            shopping_list.status = params.status

        # Update new sharing/deadline fields
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

        self.database.db.commit()
        self.database.db.refresh(shopping_list)

        # Build items response
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

        # Get member count
        member_count = 0
        if shopping_list.is_shared:
            member_count = len(
                [m for m in shopping_list.members if m.archived_at is None]
            )

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
                items=items,
                created_at=shopping_list.created_at,
                updated_at=shopping_list.updated_at,
            )
        )

    class Params(BaseModel):
        name: str | None = None
        status: str | None = None
        # New fields
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
        items: list["UpdateShoppingList.ItemResponse"] = []
        created_at: datetime
        updated_at: datetime
