"""Assign shopping list item to a user endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class AssignItem(Endpoint):
    """Assign a shopping list item to a specific user."""

    def execute(
        self,
        list_id: str,
        item_id: str,
        params: "AssignItem.Params",
    ):
        """
        Assign an item to a specific member for them to pick up.

        Args:
            list_id: The shopping list's ID
            item_id: The item's ID
            params: Assignment parameters

        Returns:
            Updated item with assignment info
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
                detail="You don't have permission to assign items",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Find item
        item = self.database.find_by(
            ShoppingListItem, id=item_id, shopping_list_id=list_id
        )
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Item with ID '{item_id}' not found",
                code=ErrorCode.SHOPPING_LIST_ITEM_NOT_FOUND,
            )

        # Validate assignee is a member (if assigning)
        assignee = None
        if params.user_id:
            # Check if assignee is owner
            if str(shopping_list.owner_id) == params.user_id:
                assignee = self.database.find_by(User, id=params.user_id)
            else:
                # Check if assignee is a member
                assignee_membership = self.database.find_by(
                    ShoppingListUser,
                    shopping_list_id=list_id,
                    user_id=params.user_id,
                )
                if not assignee_membership or assignee_membership.archived_at:
                    raise APIException(
                        status_code=400,
                        detail="Cannot assign to non-member",
                        code=ErrorCode.SHOPPING_LIST_MEMBER_NOT_FOUND,
                    )
                assignee = self.database.find_by(User, id=params.user_id)

            if not assignee:
                raise APIException(
                    status_code=404,
                    detail="Assignee not found",
                    code=ErrorCode.USER_NOT_FOUND,
                )

        # Update assignment
        item.assigned_to_user_id = params.user_id
        self.database.db.commit()
        self.database.db.refresh(item)

        return success(
            data=AssignItem.Response(
                id=str(item.id),
                name=item.name,
                assigned_to_user_id=str(item.assigned_to_user_id)
                if item.assigned_to_user_id
                else None,
                assigned_to_user_name=assignee.name if assignee else None,
            )
        )

    class Params(BaseModel):
        user_id: str | None = None  # None to unassign

    class Response(BaseModel):
        id: str
        name: str
        assigned_to_user_id: str | None = None
        assigned_to_user_name: str | None = None


class BulkAssignItems(Endpoint):
    """Bulk assign shopping list items to users."""

    def execute(
        self,
        list_id: str,
        params: "BulkAssignItems.Params",
    ):
        """
        Assign multiple items to users in one request.

        Useful for splitting a shopping list between multiple shoppers.

        Args:
            list_id: The shopping list's ID
            params: Bulk assignment parameters

        Returns:
            Summary of assignments made
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
                detail="You don't have permission to assign items",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Process assignments
        assigned_count = 0
        errors = []

        for assignment in params.assignments:
            item = self.database.find_by(
                ShoppingListItem, id=assignment.item_id, shopping_list_id=list_id
            )
            if not item:
                errors.append(f"Item {assignment.item_id} not found")
                continue

            # Validate assignee if provided
            if assignment.user_id:
                is_valid_assignee = (
                    str(shopping_list.owner_id) == assignment.user_id
                    or self.database.find_by(
                        ShoppingListUser,
                        shopping_list_id=list_id,
                        user_id=assignment.user_id,
                    )
                    is not None
                )
                if not is_valid_assignee:
                    errors.append(
                        f"User {assignment.user_id} is not a member for item {assignment.item_id}"
                    )
                    continue

            item.assigned_to_user_id = assignment.user_id
            assigned_count += 1

        self.database.db.commit()

        return success(
            data=BulkAssignItems.Response(
                assigned_count=assigned_count,
                error_count=len(errors),
                errors=errors if errors else None,
            )
        )

    class ItemAssignment(BaseModel):
        item_id: str
        user_id: str | None = None

    class Params(BaseModel):
        assignments: list["BulkAssignItems.ItemAssignment"]

    class Response(BaseModel):
        assigned_count: int
        error_count: int
        errors: list[str] | None = None
