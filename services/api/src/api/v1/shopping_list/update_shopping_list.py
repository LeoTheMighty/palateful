"""Update shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.user import User

VALID_STATUSES = ["pending", "in_progress", "completed"]


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

        # Check access
        if shopping_list.owner_id != user.id:
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

        # Update fields
        if params.name is not None:
            shopping_list.name = params.name
        if params.status is not None:
            shopping_list.status = params.status

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
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
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
                items=items,
                created_at=shopping_list.created_at,
                updated_at=shopping_list.updated_at,
            )
        )

    class Params(BaseModel):
        name: str | None = None
        status: str | None = None

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        category: str | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        id: str
        name: str | None = None
        status: str
        meal_event_id: str | None = None
        pantry_id: str | None = None
        owner_id: str
        items: list["UpdateShoppingList.ItemResponse"] = []
        created_at: datetime
        updated_at: datetime
