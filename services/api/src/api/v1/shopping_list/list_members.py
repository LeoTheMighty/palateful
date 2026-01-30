"""List shopping list members endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class ListShoppingListMembers(Endpoint):
    """Get all members of a shopping list."""

    def execute(self, list_id: str):
        """
        Get all members of a shopping list.

        Args:
            list_id: The shopping list's ID

        Returns:
            List of members with their roles
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

        # Check access - must be owner or member
        is_owner = shopping_list.owner_id == user.id
        membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=user.id
        )
        if not is_owner and not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Build members list
        members = []
        for member in shopping_list.members:
            if member.archived_at is None:
                member_user = member.user
                members.append(
                    ListShoppingListMembers.MemberResponse(
                        user_id=str(member.user_id),
                        email=member_user.email if member_user else None,
                        name=member_user.name if member_user else None,
                        picture=member_user.picture if member_user else None,
                        role=member.role,
                        notify_on_add=member.notify_on_add,
                        notify_on_check=member.notify_on_check,
                        notify_on_deadline=member.notify_on_deadline,
                        last_seen_at=member.last_seen_at,
                        joined_at=member.created_at,
                    )
                )

        # Also include owner if not in members list
        owner_in_members = any(m.user_id == shopping_list.owner_id for m in members)
        if not owner_in_members:
            owner = shopping_list.owner
            members.insert(
                0,
                ListShoppingListMembers.MemberResponse(
                    user_id=str(shopping_list.owner_id),
                    email=owner.email if owner else None,
                    name=owner.name if owner else None,
                    picture=owner.picture if owner else None,
                    role="owner",
                    notify_on_add=True,
                    notify_on_check=False,
                    notify_on_deadline=True,
                    last_seen_at=None,
                    joined_at=shopping_list.created_at,
                ),
            )

        return success(
            data=ListShoppingListMembers.Response(
                members=members,
                total=len(members),
                is_shared=shopping_list.is_shared,
                share_code=shopping_list.share_code,
            )
        )

    class MemberResponse(BaseModel):
        user_id: str
        email: str | None = None
        name: str | None = None
        picture: str | None = None
        role: str
        notify_on_add: bool
        notify_on_check: bool
        notify_on_deadline: bool
        last_seen_at: datetime | None = None
        joined_at: datetime

    class Response(BaseModel):
        members: list["ListShoppingListMembers.MemberResponse"]
        total: int
        is_shared: bool
        share_code: str | None = None
