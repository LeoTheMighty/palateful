"""Delete shopping list endpoint."""

from datetime import UTC, datetime

from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.user import User


class DeleteShoppingList(AsyncEndpoint):
    """Delete (archive) a shopping list."""

    async def execute(self, list_id: str):
        """
        Delete (archive) a shopping list.

        Only the owner can delete a shopping list.

        Args:
            list_id: The shopping list's ID

        Returns:
            Success acknowledgment
        """
        user: User = self.user

        shopping_list = await self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        if shopping_list.owner_id != user.id:
            raise APIException(
                status_code=403,
                detail="Only the owner can delete this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Auto-recovery: if deleting the default list, restore previous
        restored_default_id = None
        if str(shopping_list.id) == str(user.default_shopping_list_id or ""):
            user.default_shopping_list_id = user.previous_shopping_list_id
            user.previous_shopping_list_id = None
            restored_default_id = str(user.default_shopping_list_id) if user.default_shopping_list_id else None

        shopping_list.archived_at = datetime.now(UTC)
        await self.database.db.commit()

        return success(data={
            "deleted": True,
            "id": str(list_id),
            "restored_default_shopping_list_id": restored_default_id,
        })
