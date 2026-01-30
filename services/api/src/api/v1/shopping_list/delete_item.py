"""Delete shopping list item endpoint."""

from datetime import datetime

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class DeleteShoppingListItem(Endpoint):
    """Delete (archive) a shopping list item."""

    def execute(self, list_id: str, item_id: str):
        """
        Delete (archive) a shopping list item.

        Args:
            list_id: The shopping list's ID
            item_id: The item's ID

        Returns:
            Success acknowledgment
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
                detail="You don't have permission to delete items from this shopping list",
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

        # Soft delete
        item.archived_at = datetime.now(datetime.UTC)
        self.database.db.commit()

        # TODO: Create ShoppingListEvent for item_removed

        return success(data={"deleted": True, "id": str(item_id)})
