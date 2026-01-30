"""Update shopping list item endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.user import User


class UpdateShoppingListItem(Endpoint):
    """Update a shopping list item."""

    def execute(self, list_id: str, item_id: str, params: "UpdateShoppingListItem.Params"):
        """
        Update a shopping list item.

        Args:
            list_id: The shopping list's ID
            item_id: The item's ID
            params: Update parameters

        Returns:
            Updated item data
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
                detail="You don't have permission to update items in this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Find item
        item = self.database.find_by(
            ShoppingListItem, id=item_id, shopping_list_id=list_id
        )
        if not item or item.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Item with ID '{item_id}' not found",
                code=ErrorCode.SHOPPING_LIST_ITEM_NOT_FOUND,
            )

        # Update fields
        if params.name is not None:
            item.name = params.name
        if params.quantity is not None:
            item.quantity = params.quantity
        if params.unit is not None:
            item.unit = params.unit
        if params.category is not None:
            item.category = params.category
        if params.is_checked is not None:
            item.is_checked = params.is_checked
            if params.is_checked:
                item.checked_by_user_id = user.id
            else:
                item.checked_by_user_id = None

        self.database.db.commit()
        self.database.db.refresh(item)

        return success(
            data=UpdateShoppingListItem.Response(
                id=str(item.id),
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                is_checked=item.is_checked,
                checked_by_user_id=(
                    str(item.checked_by_user_id) if item.checked_by_user_id else None
                ),
                category=item.category,
                ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
                recipe_id=str(item.recipe_id) if item.recipe_id else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    class Params(BaseModel):
        name: str | None = None
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool | None = None
        category: str | None = None

    class Response(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        checked_by_user_id: str | None = None
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None
        created_at: datetime
        updated_at: datetime
