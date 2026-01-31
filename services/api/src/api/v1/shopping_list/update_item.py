"""Update shopping list item endpoint."""

from datetime import datetime
from decimal import Decimal

from api.v1.shopping_list.utils.notifications import (
    notify_item_checked,
    notify_list_complete,
)
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
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

        # Update basic fields
        if params.name is not None:
            item.name = params.name
        if params.quantity is not None:
            item.quantity = params.quantity
        if params.unit is not None:
            item.unit = params.unit
        if params.category is not None:
            item.category = params.category

        # Handle check/uncheck with timestamp
        if params.is_checked is not None:
            item.is_checked = params.is_checked
            if params.is_checked:
                item.checked_by_user_id = user.id
                item.checked_at = datetime.now(datetime.UTC)
            else:
                item.checked_by_user_id = None
                item.checked_at = None

        # Update new deadline/collaboration fields
        if params.due_at is not None:
            item.due_at = params.due_at
        if params.meal_event_id is not None:
            item.meal_event_id = params.meal_event_id
        if params.due_reason is not None:
            item.due_reason = params.due_reason
        if params.priority is not None:
            item.priority = params.priority
        if params.notes is not None:
            item.notes = params.notes
        if params.assigned_to_user_id is not None:
            item.assigned_to_user_id = params.assigned_to_user_id
        if params.store_section is not None:
            item.store_section = params.store_section
        if params.store_order is not None:
            item.store_order = params.store_order

        self.database.db.commit()
        self.database.db.refresh(item)

        # Send notification when item is checked off
        if params.is_checked is True:
            notify_item_checked(shopping_list, item, user, self.database)

            # Check if all items are now complete
            unchecked_count = (
                self.database.db.query(ShoppingListItem)
                .filter(
                    ShoppingListItem.shopping_list_id == shopping_list.id,
                    ShoppingListItem.is_checked.is_(False),
                    ShoppingListItem.archived_at.is_(None),
                )
                .count()
            )
            if unchecked_count == 0:
                notify_list_complete(shopping_list, user, self.database)

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
                # New fields
                due_at=item.due_at,
                meal_event_id=str(item.meal_event_id) if item.meal_event_id else None,
                due_reason=item.due_reason,
                priority=item.priority,
                added_by_user_id=(
                    str(item.added_by_user_id) if item.added_by_user_id else None
                ),
                notes=item.notes,
                checked_at=item.checked_at,
                assigned_to_user_id=(
                    str(item.assigned_to_user_id) if item.assigned_to_user_id else None
                ),
                store_section=item.store_section,
                store_order=item.store_order,
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
        # New deadline/collaboration fields
        due_at: datetime | None = None
        meal_event_id: str | None = None
        due_reason: str | None = None
        priority: int | None = None
        notes: str | None = None
        assigned_to_user_id: str | None = None
        store_section: str | None = None
        store_order: int | None = None

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
        # New fields
        due_at: datetime | None = None
        meal_event_id: str | None = None
        due_reason: str | None = None
        priority: int = 3
        added_by_user_id: str | None = None
        notes: str | None = None
        checked_at: datetime | None = None
        assigned_to_user_id: str | None = None
        store_section: str | None = None
        store_order: int | None = None
        created_at: datetime
        updated_at: datetime
