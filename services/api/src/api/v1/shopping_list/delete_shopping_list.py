"""Delete shopping list endpoint."""

from datetime import datetime

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.user import User


class DeleteShoppingList(Endpoint):
    """Delete (archive) a shopping list."""

    def execute(self, list_id: str):
        """
        Delete (archive) a shopping list.

        Args:
            list_id: The shopping list's ID

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

        # Check access
        if shopping_list.owner_id != user.id:
            raise APIException(
                status_code=403,
                detail="Only the owner can delete this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Soft delete
        shopping_list.archived_at = datetime.utcnow()
        self.database.db.commit()

        return success(data={"deleted": True, "id": str(list_id)})
