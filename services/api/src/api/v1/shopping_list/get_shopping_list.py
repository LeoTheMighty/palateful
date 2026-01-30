"""Get shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class GetShoppingList(Endpoint):
    """Get a shopping list by ID."""

    def execute(self, list_id: str):
        """
        Get a shopping list by ID.

        Args:
            list_id: The shopping list's ID

        Returns:
            Shopping list data
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

        # Check access - owner or member
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

        # Update last_seen_at for the member
        if membership:
            membership.last_seen_at = datetime.utcnow()
            self.database.db.commit()

        # Build items response
        items = []
        for item in shopping_list.items:
            if item.archived_at is None:
                items.append(
                    GetShoppingList.ItemResponse(
                        id=str(item.id),
                        name=item.name,
                        quantity=item.quantity,
                        unit=item.unit,
                        is_checked=item.is_checked,
                        checked_by_user_id=(
                            str(item.checked_by_user_id)
                            if item.checked_by_user_id
                            else None
                        ),
                        recipe_id=str(item.recipe_id) if item.recipe_id else None,
                        already_have_quantity=item.already_have_quantity,
                        category=item.category,
                        ingredient_id=(
                            str(item.ingredient_id) if item.ingredient_id else None
                        ),
                        # New deadline/collaboration fields
                        due_at=item.due_at,
                        meal_event_id=(
                            str(item.meal_event_id) if item.meal_event_id else None
                        ),
                        due_reason=item.due_reason,
                        priority=item.priority,
                        added_by_user_id=(
                            str(item.added_by_user_id) if item.added_by_user_id else None
                        ),
                        notes=item.notes,
                        checked_at=item.checked_at,
                        assigned_to_user_id=(
                            str(item.assigned_to_user_id)
                            if item.assigned_to_user_id
                            else None
                        ),
                        store_section=item.store_section,
                        store_order=item.store_order,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                )

        # Get member count if shared
        member_count = 0
        if shopping_list.is_shared:
            member_count = len(
                [m for m in shopping_list.members if m.archived_at is None]
            )

        return success(
            data=GetShoppingList.Response(
                id=str(shopping_list.id),
                name=shopping_list.name,
                status=shopping_list.status,
                meal_event_id=(
                    str(shopping_list.meal_event_id)
                    if shopping_list.meal_event_id
                    else None
                ),
                pantry_id=(
                    str(shopping_list.pantry_id) if shopping_list.pantry_id else None
                ),
                owner_id=str(shopping_list.owner_id),
                is_shared=shopping_list.is_shared,
                share_code=shopping_list.share_code,
                default_deadline=shopping_list.default_deadline,
                sort_by=shopping_list.sort_by,
                member_count=member_count,
                current_user_role=membership.role if membership else "owner",
                items=items,
                created_at=shopping_list.created_at,
                updated_at=shopping_list.updated_at,
            )
        )

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        checked_by_user_id: str | None = None
        recipe_id: str | None = None
        already_have_quantity: Decimal | None = None
        category: str | None = None
        ingredient_id: str | None = None
        # New deadline/collaboration fields
        due_at: datetime | None = None
        meal_event_id: str | None = None
        due_reason: str | None = None
        priority: int = 3
        added_by_user_id: str | None = None
        notes: str | None = None
        checked_at: datetime | None = None
        assigned_to_user_id: str | None = None
        store_section: str | None = None
        store_order: int | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        id: str
        name: str | None = None
        status: str
        meal_event_id: str | None = None
        pantry_id: str | None = None
        owner_id: str
        is_shared: bool = False
        share_code: str | None = None
        default_deadline: datetime | None = None
        sort_by: str = "deadline"
        member_count: int = 0
        current_user_role: str = "owner"
        items: list["GetShoppingList.ItemResponse"] = []
        created_at: datetime
        updated_at: datetime
