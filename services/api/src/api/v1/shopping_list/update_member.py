"""Update shopping list member endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class UpdateShoppingListMember(AsyncEndpoint):
    """Update a member's role or notification settings."""

    async def execute(
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

        shopping_list = await self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        target_result = await self.db.execute(
            select(ShoppingListUser)
            .options(selectinload(ShoppingListUser.user))
            .where(ShoppingListUser.shopping_list_id == list_id)
            .where(ShoppingListUser.user_id == member_user_id)
        )
        target_membership = target_result.scalars().first()
        if not target_membership or target_membership.archived_at:
            raise APIException(
                status_code=404,
                detail="Member not found in this shopping list",
                code=ErrorCode.SHOPPING_LIST_MEMBER_NOT_FOUND,
            )

        is_self_update = str(user.id) == member_user_id

        if params.role is not None and not is_self_update:
            is_owner = shopping_list.owner_id == user.id
            if not is_owner:
                raise APIException(
                    status_code=403,
                    detail="Only the owner can change member roles",
                    code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
                )

            if target_membership.role == "owner":
                raise APIException(
                    status_code=400,
                    detail="Cannot change the owner's role",
                    code=ErrorCode.SHOPPING_LIST_CANNOT_REMOVE_OWNER,
                )

        if params.role is not None:
            target_membership.role = params.role

        if params.notify_on_add is not None:
            target_membership.notify_on_add = params.notify_on_add

        if params.notify_on_check is not None:
            target_membership.notify_on_check = params.notify_on_check

        if params.notify_on_deadline is not None:
            target_membership.notify_on_deadline = params.notify_on_deadline

        await self.database.db.commit()
        await self.database.db.refresh(target_membership)

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
