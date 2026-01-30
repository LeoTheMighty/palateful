"""Create shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.user import User


class CreateShoppingList(Endpoint):
    """Create a new shopping list."""

    def execute(self, params: "CreateShoppingList.Params"):
        """
        Create a new shopping list.

        Args:
            params: Shopping list creation parameters

        Returns:
            Created shopping list data
        """
        user: User = self.user

        # Create shopping list
        shopping_list = ShoppingList(
            name=params.name,
            meal_event_id=params.meal_event_id,
            pantry_id=params.pantry_id,
            owner_id=user.id,
        )
        self.database.create(shopping_list)
        self.database.db.refresh(shopping_list)

        # Add items if provided
        item_responses = []
        for item_input in params.items:
            item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=item_input.name,
                quantity=item_input.quantity,
                unit=item_input.unit,
                category=item_input.category,
                ingredient_id=item_input.ingredient_id,
                recipe_id=item_input.recipe_id,
            )
            self.database.create(item)
            self.database.db.refresh(item)
            item_responses.append(
                CreateShoppingList.ItemResponse(
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
                )
            )

        return success(
            data=CreateShoppingList.Response(
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
                items=item_responses,
                created_at=shopping_list.created_at,
                updated_at=shopping_list.updated_at,
            ),
            status=201,
        )

    class ItemInput(BaseModel):
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None

    class Params(BaseModel):
        name: str | None = None
        meal_event_id: str | None = None
        pantry_id: str | None = None
        items: list["CreateShoppingList.ItemInput"] = []

    class ItemResponse(BaseModel):
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

    class Response(BaseModel):
        id: str
        name: str | None = None
        status: str
        meal_event_id: str | None = None
        pantry_id: str | None = None
        owner_id: str
        items: list["CreateShoppingList.ItemResponse"] = []
        created_at: datetime
        updated_at: datetime
