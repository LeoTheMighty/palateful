"""Get shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.user import User


class GetShoppingList(Endpoint):
    """Get a shopping list by ID."""

    def execute(self, list_id: str):
        """
        Get a shopping list by ID.

        Args:
            list_id: The shopping list's ID

        Returns:
            Shopping list data
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

        # Check access - must be owner
        if shopping_list.owner_id != user.id:
            raise APIException(
                status_code=403,
                detail="You don't have access to this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Build items response
        items = []
        for item in shopping_list.items:
            if item.archived_at is None:
                items.append(
                    GetShoppingList.ItemResponse(
                        id=str(item.id),
                        name=item.name,
                        quantity=item.quantity,
                        unit=item.unit,
                        is_checked=item.is_checked,
                        checked_by_user_id=(
                            str(item.checked_by_user_id)
                            if item.checked_by_user_id
                            else None
                        ),
                        recipe_id=str(item.recipe_id) if item.recipe_id else None,
                        already_have_quantity=item.already_have_quantity,
                        category=item.category,
                        ingredient_id=(
                            str(item.ingredient_id) if item.ingredient_id else None
                        ),
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                )

        return success(
            data=GetShoppingList.Response(
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

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        checked_by_user_id: str | None = None
        recipe_id: str | None = None
        already_have_quantity: Decimal | None = None
        category: str | None = None
        ingredient_id: str | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        id: str
        name: str | None = None
        status: str
        meal_event_id: str | None = None
        pantry_id: str | None = None
        owner_id: str
        items: list["GetShoppingList.ItemResponse"] = []
        created_at: datetime
        updated_at: datetime
