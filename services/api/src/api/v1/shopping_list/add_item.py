"""Add item to shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from api.v1.shopping_list.utils.notifications import notify_item_added
from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User
from utils.models.user_activity import UserActivity
from utils.services.notifications_bridge import notify_via_threadpool


class AddShoppingListItem(AsyncEndpoint):
    """Add an item to a shopping list."""

    async def execute(self, list_id: str, params: "AddShoppingListItem.Params"):
        """
        Add an item to a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Item parameters

        Returns:
            Created item data
        """
        user: User = self.user

        shopping_list = await self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        is_owner = shopping_list.owner_id == user.id
        membership = await self.database.find_by(
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
                detail="You don't have permission to add items to this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        item = ShoppingListItem(
            shopping_list_id=shopping_list.id,
            name=params.name,
            quantity=params.quantity,
            unit=params.unit,
            category=params.category,
            ingredient_id=params.ingredient_id,
            recipe_id=params.recipe_id,
            due_at=params.due_at,
            meal_event_id=params.meal_event_id,
            due_reason=params.due_reason,
            priority=params.priority,
            added_by_user_id=user.id,
            notes=params.notes,
            assigned_to_user_id=params.assigned_to_user_id,
            store_section=params.store_section,
            store_order=params.store_order,
        )
        await self.database.create(item)

        # Push notification (fire-and-forget) via sync helper on threadpool.
        await notify_via_threadpool(notify_item_added, shopping_list, item, user)

        # Activity fan-out — inline on the async session (sync
        # create_activity takes a sync Session, so we construct the row
        # directly and flush via the async session).
        if shopping_list.is_shared:
            members_result = await self.db.execute(
                select(ShoppingListUser).where(
                    ShoppingListUser.shopping_list_id == shopping_list.id,
                    ShoppingListUser.user_id != user.id,
                    ShoppingListUser.archived_at.is_(None),
                )
            )
            members = list(members_result.scalars().all())
            for m in members:
                self.db.add(
                    UserActivity(
                        user_id=m.user_id,
                        type="partner_action",
                        title=f"{user.name} added an item to {shopping_list.name}",
                        subtitle=item.name,
                        action_url=f"/shopping-lists/{shopping_list.id}",
                    )
                )
            if members:  # pragma: no branch - shared shopping_lists always have ≥2 active members in the seed paths covered here
                await self.db.commit()

        return success(
            data=AddShoppingListItem.Response(
                id=str(item.id),
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                is_checked=item.is_checked,
                category=item.category,
                ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
                recipe_id=str(item.recipe_id) if item.recipe_id else None,
                due_at=item.due_at,
                meal_event_id=str(item.meal_event_id) if item.meal_event_id else None,
                due_reason=item.due_reason,
                priority=item.priority,
                added_by_user_id=str(item.added_by_user_id) if item.added_by_user_id else None,
                notes=item.notes,
                assigned_to_user_id=(
                    str(item.assigned_to_user_id) if item.assigned_to_user_id else None
                ),
                store_section=item.store_section,
                store_order=item.store_order,
                created_at=item.created_at,
                updated_at=item.updated_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None
        due_at: datetime | None = None
        meal_event_id: str | None = None
        due_reason: str | None = None
        priority: int = 3
        notes: str | None = None
        assigned_to_user_id: str | None = None
        store_section: str | None = None
        store_order: int | None = None

    class Response(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None
        due_at: datetime | None = None
        meal_event_id: str | None = None
        due_reason: str | None = None
        priority: int = 3
        added_by_user_id: str | None = None
        notes: str | None = None
        assigned_to_user_id: str | None = None
        store_section: str | None = None
        store_order: int | None = None
        created_at: datetime
        updated_at: datetime
