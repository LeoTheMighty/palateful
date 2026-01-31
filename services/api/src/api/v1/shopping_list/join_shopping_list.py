"""Join shopping list via share code endpoint."""

from datetime import datetime

from api.v1.shopping_list.utils.notifications import notify_member_joined
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class JoinShoppingList(Endpoint):
    """Join a shopping list using a share code."""

    def execute(self, share_code: str):
        """
        Join a shopping list via share code.

        Args:
            share_code: The share code for the list

        Returns:
            Shopping list data
        """
        user: User = self.user

        # Find shopping list by share code
        shopping_list = self.database.find_by(
            ShoppingList, share_code=share_code.upper()
        )
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail="Invalid or expired share code",
                code=ErrorCode.SHOPPING_LIST_INVALID_SHARE_CODE,
            )

        # Check if already a member
        existing = self.database.find_by(
            ShoppingListUser, shopping_list_id=shopping_list.id, user_id=user.id
        )
        if existing:
            raise APIException(
                status_code=400,
                detail="You are already a member of this shopping list",
                code=ErrorCode.SHOPPING_LIST_ALREADY_MEMBER,
            )

        # Check member limit (optional, configurable)
        member_count = len(
            [m for m in shopping_list.members if m.archived_at is None]
        )
        if member_count >= 10:  # Max 10 members per list
            raise APIException(
                status_code=400,
                detail="This shopping list has reached the maximum number of members",
                code=ErrorCode.SHOPPING_LIST_SHARE_LIMIT_REACHED,
            )

        # Create membership
        membership = ShoppingListUser(
            shopping_list_id=shopping_list.id,
            user_id=user.id,
            role="editor",  # New members default to editor
        )
        self.database.create(membership)
        self.database.db.refresh(membership)

        # Notify existing members about new member
        notify_member_joined(shopping_list, user, self.database)

        return success(
            data=JoinShoppingList.Response(
                shopping_list_id=str(shopping_list.id),
                name=shopping_list.name,
                role=membership.role,
                member_count=member_count + 1,
                joined_at=membership.created_at,
            ),
            status=201,
        )

    class Response(BaseModel):
        shopping_list_id: str
        name: str | None = None
        role: str
        member_count: int
        joined_at: datetime
