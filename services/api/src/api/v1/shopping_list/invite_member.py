"""Invite member to shopping list endpoint."""

from datetime import datetime

from api.v1.shopping_list.utils.notifications import notify_list_shared
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class InviteShoppingListMember(Endpoint):
    """Invite a user to a shopping list by email or user ID."""

    def execute(self, list_id: str, params: "InviteShoppingListMember.Params"):
        """
        Invite a user to a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Invitation parameters (user_id or email)

        Returns:
            Member data
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

        # Check access - must be owner or editor
        is_owner = shopping_list.owner_id == user.id
        current_membership = self.database.find_by(
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

        # Find the user to invite
        invited_user = None
        if params.user_id:
            invited_user = self.database.find_by(User, id=params.user_id)
        elif params.email:
            invited_user = self.database.find_by(User, email=params.email)

        if not invited_user:
            raise APIException(
                status_code=404,
                detail="User not found",
                code=ErrorCode.USER_NOT_FOUND,
            )

        # Check if already a member
        existing = self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=invited_user.id
        )
        if existing and not existing.archived_at:
            raise APIException(
                status_code=400,
                detail="User is already a member of this shopping list",
                code=ErrorCode.SHOPPING_LIST_ALREADY_MEMBER,
            )

        # Check member limit
        member_count = len(
            [m for m in shopping_list.members if m.archived_at is None]
        )
        if member_count >= 10:
            raise APIException(
                status_code=400,
                detail="This shopping list has reached the maximum number of members",
                code=ErrorCode.SHOPPING_LIST_SHARE_LIMIT_REACHED,
            )

        # Create or reactivate membership
        if existing and existing.archived_at:
            # Reactivate archived membership
            existing.archived_at = None
            existing.role = params.role
            self.database.db.commit()
            membership = existing
        else:
            # Create new membership
            membership = ShoppingListUser(
                shopping_list_id=shopping_list.id,
                user_id=invited_user.id,
                role=params.role,
            )
            self.database.create(membership)

        self.database.db.refresh(membership)

        # Mark list as shared if not already
        if not shopping_list.is_shared:
            shopping_list.is_shared = True
            self.database.db.commit()

        # Ensure owner has membership record
        owner_membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=shopping_list.id, user_id=shopping_list.owner_id
        )
        if not owner_membership:
            owner_membership = ShoppingListUser(
                shopping_list_id=shopping_list.id,
                user_id=shopping_list.owner_id,
                role="owner",
            )
            self.database.create(owner_membership)

        # Send notification to invited user
        notify_list_shared(shopping_list, invited_user, user, self.database)

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
