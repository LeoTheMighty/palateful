"""Add item to shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.user import User


class AddShoppingListItem(Endpoint):
    """Add an item to a shopping list."""

    def execute(self, list_id: str, params: "AddShoppingListItem.Params"):
        """
        Add an item to a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Item parameters

        Returns:
            Created item data
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
                detail="You don't have permission to add items to this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Create item
        item = ShoppingListItem(
            shopping_list_id=shopping_list.id,
            name=params.name,
            quantity=params.quantity,
            unit=params.unit,
            category=params.category,
            ingredient_id=params.ingredient_id,
            recipe_id=params.recipe_id,
        )
        self.database.create(item)
        self.database.db.refresh(item)

        return success(
            data=AddShoppingListItem.Response(
                id=str(item.id),
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                is_checked=item.is_checked,
                category=item.category,
                ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
                recipe_id=str(item.recipe_id) if item.recipe_id else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None

    class Response(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None
        created_at: datetime
        updated_at: datetime
