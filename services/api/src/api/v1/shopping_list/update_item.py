"""Update shopping list item endpoint."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from api.v1.shopping_list.utils.notifications import (
    notify_item_checked,
    notify_list_complete,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.events import ShoppingListItemPurchased, dispatch
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User
from utils.services.notifications_bridge import notify_via_threadpool

logger = logging.getLogger(__name__)


class UpdateShoppingListItem(AsyncEndpoint):
    """Update a shopping list item."""

    async def execute(
        self, list_id: str, item_id: str, params: "UpdateShoppingListItem.Params"
    ):
        """
        Update a shopping list item.

        Args:
            list_id: The shopping list's ID
            item_id: The item's ID
            params: Update parameters

        Returns:
            Updated item data
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
                detail="You don't have permission to update items in this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        item = await self.database.find_by(
            ShoppingListItem, id=item_id, shopping_list_id=list_id
        )
        if not item or item.archived_at is not None:
            raise APIException(
                status_code=404,
                detail=f"Item with ID '{item_id}' not found",
                code=ErrorCode.SHOPPING_LIST_ITEM_NOT_FOUND,
            )

        # Capture pre-update state for event dispatch (pantry-3 hook).
        previous_is_checked = item.is_checked

        if params.name is not None:
            item.name = params.name
        if params.quantity is not None:
            item.quantity = params.quantity
        if params.unit is not None:
            item.unit = params.unit
        if params.category is not None:
            item.category = params.category

        if params.is_checked is not None:
            item.is_checked = params.is_checked
            if params.is_checked:
                item.checked_by_user_id = user.id
                item.checked_at = datetime.now(UTC)
            else:
                item.checked_by_user_id = None
                item.checked_at = None

        if params.due_at is not None:
            item.due_at = params.due_at
        if params.meal_event_id is not None:
            item.meal_event_id = params.meal_event_id
        if params.due_reason is not None:
            item.due_reason = params.due_reason
        if params.priority is not None:
            item.priority = params.priority
        if params.notes is not None:
            item.notes = params.notes
        if params.assigned_to_user_id is not None:
            item.assigned_to_user_id = params.assigned_to_user_id
        if params.store_section is not None:
            item.store_section = params.store_section
        if params.store_order is not None:
            item.store_order = params.store_order

        await self.database.db.commit()
        await self.database.db.refresh(item)

        # Pantry auto-add hook (pantry-3): only fire on the false → true
        # transition AND when we have a resolved ingredient. Free-text items
        # skip entirely. A failure here must not break the user's check-off.
        #
        # pantry_service is still sync (aam-15 in progress); bridge through
        # run_in_threadpool on a fresh short-lived sync session. Snapshot
        # the scalar attrs the sync helpers need so the sync session never
        # accesses the async ORM instance.
        pantry_ingredient_id: str | None = None
        pantry_id: str | None = None
        if (
            params.is_checked is True
            and previous_is_checked is False
            and item.ingredient_id is not None
        ):
            user_id_snapshot = user.id
            ingredient_id_snapshot = item.ingredient_id
            quantity_snapshot = item.quantity
            unit_snapshot = item.unit

            def _pantry_sync_add() -> tuple[str | None, str | None]:
                from utils.services.database import Database, SessionLocal
                from utils.services.pantry_service import (
                    get_or_create_default_pantry,
                    upsert_pantry_ingredient,
                )

                sync_db = Database(db=SessionLocal())
                try:
                    pantry, _m = get_or_create_default_pantry(
                        user_id_snapshot, sync_db
                    )
                    result = upsert_pantry_ingredient(
                        sync_db,
                        pantry_id=pantry.id,
                        ingredient_id=ingredient_id_snapshot,
                        quantity_display=quantity_snapshot,
                        unit_display=unit_snapshot,
                        quantity_normalized=quantity_snapshot,
                        unit_normalized=unit_snapshot,
                    )
                    if result.skipped_reason is None:  # pragma: no branch
                        return (str(pantry.id), str(ingredient_id_snapshot))
                    return (None, None)
                finally:
                    sync_db.close()

            try:
                pantry_id, pantry_ingredient_id = await run_in_threadpool(
                    _pantry_sync_add
                )
                # Domain dispatcher stays sync — in-memory only.
                dispatch(
                    "ShoppingListItemPurchased",
                    ShoppingListItemPurchased(
                        user_id=user.id,
                        shopping_list_id=shopping_list.id,
                        item_id=item.id,
                        ingredient_id=item.ingredient_id,
                        quantity_normalized=(
                            Decimal(item.quantity) if item.quantity is not None else None
                        ),
                        unit_normalized=item.unit,
                        shopping_list_item_name=item.name,
                    ),
                )
            except Exception:
                # Best-effort: never block the user on the side effect.
                logger.exception(
                    "pantry_auto_add_failed user_id=%s item_id=%s", user.id, item_id
                )

        if params.is_checked is True:
            await notify_via_threadpool(
                notify_item_checked, shopping_list, item, user
            )

            unchecked_count_result = await self.db.execute(
                select(func.count())
                .select_from(ShoppingListItem)
                .where(
                    ShoppingListItem.shopping_list_id == shopping_list.id,
                    ShoppingListItem.is_checked.is_(False),
                    ShoppingListItem.archived_at.is_(None),
                )
            )
            unchecked_count = int(unchecked_count_result.scalar() or 0)
            if unchecked_count == 0:
                await notify_via_threadpool(
                    notify_list_complete, shopping_list, user
                )

        return success(
            data=UpdateShoppingListItem.Response(
                id=str(item.id),
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                is_checked=item.is_checked,
                checked_by_user_id=(
                    str(item.checked_by_user_id) if item.checked_by_user_id else None
                ),
                category=item.category,
                ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
                recipe_id=str(item.recipe_id) if item.recipe_id else None,
                due_at=item.due_at,
                meal_event_id=str(item.meal_event_id) if item.meal_event_id else None,
                due_reason=item.due_reason,
                priority=item.priority,
                added_by_user_id=(
                    str(item.added_by_user_id) if item.added_by_user_id else None
                ),
                notes=item.notes,
                checked_at=item.checked_at,
                assigned_to_user_id=(
                    str(item.assigned_to_user_id) if item.assigned_to_user_id else None
                ),
                store_section=item.store_section,
                store_order=item.store_order,
                created_at=item.created_at,
                updated_at=item.updated_at,
                pantry_ingredient_id=pantry_ingredient_id,
                pantry_id=pantry_id,
            )
        )

    class Params(BaseModel):
        name: str | None = None
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool | None = None
        category: str | None = None
        due_at: datetime | None = None
        meal_event_id: str | None = None
        due_reason: str | None = None
        priority: int | None = None
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
        checked_by_user_id: str | None = None
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None
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
        # Pantry auto-add hook (pantry-3): populated when is_checked transitions
        # false → true and ``ingredient_id`` is set. Null otherwise.
        pantry_ingredient_id: str | None = None
        pantry_id: str | None = None
