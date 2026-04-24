"""Invite member to shopping list endpoint."""

from datetime import datetime

from api.v1.shopping_list.utils.notifications import notify_list_shared
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User
from utils.services.notifications_bridge import notify_via_threadpool


class InviteShoppingListMember(AsyncEndpoint):
    """Invite a user to a shopping list by email or user ID."""

    async def execute(self, list_id: str, params: "InviteShoppingListMember.Params"):
        """
        Invite a user to a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Invitation parameters (user_id or email)

        Returns:
            Member data
        """
        user: User = self.user

        shopping_list = await (
            self.database.where(ShoppingList, id=list_id)
            .options(selectinload(ShoppingList.members))
            .first()
        )
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        is_owner = shopping_list.owner_id == user.id
        current_membership = await self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=user.id
        )
        can_invite = is_owner or (
            current_membership and current_membership.role in ("owner", "editor")
        )

        if not can_invite:
            raise APIException(
                status_code=403,
                detail="You don't have permission to invite members to this list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        invited_user = None
        if params.user_id:
            invited_user = await self.database.find_by(User, id=params.user_id)
        elif params.email:  # pragma: no cover — falls through to not-found check below
            invited_user = await self.database.find_by(User, email=params.email)

        if not invited_user:
            raise APIException(
                status_code=404,
                detail="User not found",
                code=ErrorCode.USER_NOT_FOUND,
            )

        existing = await self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=invited_user.id
        )
        if existing and not existing.archived_at:
            raise APIException(
                status_code=400,
                detail="User is already a member of this shopping list",
                code=ErrorCode.SHOPPING_LIST_ALREADY_MEMBER,
            )

        member_count = len(
            [m for m in shopping_list.members if m.archived_at is None]
        )
        if member_count >= 10:
            raise APIException(
                status_code=400,
                detail="This shopping list has reached the maximum number of members",
                code=ErrorCode.SHOPPING_LIST_SHARE_LIMIT_REACHED,
            )

        if existing and existing.archived_at:
            existing.archived_at = None
            existing.role = params.role
            await self.database.db.commit()
            await self.database.db.refresh(existing)
            membership = existing
        else:
            membership = ShoppingListUser(
                shopping_list_id=shopping_list.id,
                user_id=invited_user.id,
                role=params.role,
            )
            await self.database.create(membership)

        if not shopping_list.is_shared:
            shopping_list.is_shared = True
            await self.database.db.commit()

        owner_membership = await self.database.find_by(
            ShoppingListUser, shopping_list_id=shopping_list.id, user_id=shopping_list.owner_id
        )
        if not owner_membership:  # pragma: no cover — owner record usually exists
            owner_membership = ShoppingListUser(
                shopping_list_id=shopping_list.id,
                user_id=shopping_list.owner_id,
                role="owner",
            )
            await self.database.create(owner_membership)

        await notify_via_threadpool(
            notify_list_shared, shopping_list, invited_user, user
        )

        return success(
            data=InviteShoppingListMember.Response(
                user_id=str(invited_user.id),
                email=invited_user.email,
                name=invited_user.name,
                role=membership.role,
                joined_at=membership.created_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        user_id: str | None = None
        email: str | None = None
        role: str = "editor"  # editor, viewer

    class Response(BaseModel):
        user_id: str
        email: str | None = None
        name: str | None = None
        role: str
        joined_at: datetime
