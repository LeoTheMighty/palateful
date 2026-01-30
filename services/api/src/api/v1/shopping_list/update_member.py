"""Update shopping list member endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class UpdateShoppingListMember(Endpoint):
    """Update a member's role or notification settings."""

    def execute(
        self, list_id: str, member_user_id: str, params: "UpdateShoppingListMember.Params"
    ):
        """
        Update a member's role or settings.

        Args:
            list_id: The shopping list's ID
            member_user_id: The user ID of the member to update
            params: Update parameters

        Returns:
            Updated member data
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

        # Find the membership to update
        target_membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=member_user_id
        )
        if not target_membership or target_membership.archived_at:
            raise APIException(
                status_code=404,
                detail="Member not found in this shopping list",
                code=ErrorCode.SHOPPING_LIST_MEMBER_NOT_FOUND,
            )

        # Check if this is a self-update (updating own settings)
        is_self_update = str(user.id) == member_user_id

        # Check permissions for role changes
        if params.role is not None and not is_self_update:
            # Only owner can change others' roles
            is_owner = shopping_list.owner_id == user.id
            if not is_owner:
                raise APIException(
                    status_code=403,
                    detail="Only the owner can change member roles",
                    code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
                )

            # Can't change owner's role
            if target_membership.role == "owner":
                raise APIException(
                    status_code=400,
                    detail="Cannot change the owner's role",
                    code=ErrorCode.SHOPPING_LIST_CANNOT_REMOVE_OWNER,
                )

        # Update fields
        if params.role is not None:
            target_membership.role = params.role

        if params.notify_on_add is not None:
            target_membership.notify_on_add = params.notify_on_add

        if params.notify_on_check is not None:
            target_membership.notify_on_check = params.notify_on_check

        if params.notify_on_deadline is not None:
            target_membership.notify_on_deadline = params.notify_on_deadline

        self.database.db.commit()
        self.database.db.refresh(target_membership)

        # Get member user info
        member_user = target_membership.user

        return success(
            data=UpdateShoppingListMember.Response(
                user_id=str(target_membership.user_id),
                email=member_user.email if member_user else None,
                name=member_user.name if member_user else None,
                role=target_membership.role,
                notify_on_add=target_membership.notify_on_add,
                notify_on_check=target_membership.notify_on_check,
                notify_on_deadline=target_membership.notify_on_deadline,
                updated_at=target_membership.updated_at,
            )
        )

    class Params(BaseModel):
        role: str | None = None  # editor, viewer (not owner)
        notify_on_add: bool | None = None
        notify_on_check: bool | None = None
        notify_on_deadline: bool | None = None

    class Response(BaseModel):
        user_id: str
        email: str | None = None
        name: str | None = None
        role: str
        notify_on_add: bool
        notify_on_check: bool
        notify_on_deadline: bool
        updated_at: datetime
