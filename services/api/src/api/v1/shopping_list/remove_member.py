"""Remove shopping list member endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class RemoveShoppingListMember(Endpoint):
    """Remove a member from a shopping list (or leave)."""

    def execute(self, list_id: str, member_user_id: str):
        """
        Remove a member from a shopping list.

        If the user removes themselves, they leave the list.
        Only owners can remove other members.

        Args:
            list_id: The shopping list's ID
            member_user_id: The user ID of the member to remove

        Returns:
            Confirmation message
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

        # Find the membership to remove
        target_membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=member_user_id
        )
        if not target_membership or target_membership.archived_at:
            raise APIException(
                status_code=404,
                detail="Member not found in this shopping list",
                code=ErrorCode.SHOPPING_LIST_MEMBER_NOT_FOUND,
            )

        # Check if this is a self-removal (leaving)
        is_leaving = str(user.id) == member_user_id
        is_owner = shopping_list.owner_id == user.id

        # Owners cannot leave their own list (must transfer ownership or delete)
        if is_leaving and target_membership.role == "owner":
            raise APIException(
                status_code=400,
                detail="The owner cannot leave the shopping list. Transfer ownership first or delete the list.",
                code=ErrorCode.SHOPPING_LIST_CANNOT_LEAVE_AS_OWNER,
            )

        # Non-owners can only remove themselves
        if not is_leaving and not is_owner:
            raise APIException(
                status_code=403,
                detail="Only the owner can remove other members",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Cannot remove the owner
        if target_membership.role == "owner" and not is_leaving:
            raise APIException(
                status_code=400,
                detail="Cannot remove the owner from the shopping list",
                code=ErrorCode.SHOPPING_LIST_CANNOT_REMOVE_OWNER,
            )

        # Soft delete the membership
        target_membership.archived_at = datetime.now(datetime.UTC)
        self.database.db.commit()

        # TODO: Create ShoppingListEvent for member_left

        action = "left" if is_leaving else "removed"
        return success(
            data=RemoveShoppingListMember.Response(
                message=f"Member has been {action} from the shopping list",
                user_id=member_user_id,
            )
        )

    class Response(BaseModel):
        message: str
        user_id: str
