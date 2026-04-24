"""List shopping lists endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class ListShoppingLists(AsyncEndpoint):
    """List shopping lists for the current user (owned and shared)."""

    async def execute(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ):
        """
        List shopping lists for the current user.

        Includes:
        - Lists owned by the user
        - Lists shared with the user (via membership)

        Args:
            limit: Maximum number of results
            offset: Pagination offset
            status: Filter by status

        Returns:
            Paginated list of shopping lists
        """
        user: User = self.user

        member_list_ids_stmt = (
            select(ShoppingListUser.shopping_list_id)
            .where(ShoppingListUser.user_id == user.id)
            .where(ShoppingListUser.archived_at.is_(None))
        )

        # Build query: owned OR member. selectinload items + members so
        # the response loop below (`sl.items`, `sl.members`) doesn't
        # trigger 2N lazy loads — bounded to two `IN`-batched queries
        # regardless of page size.
        conditions = [
            or_(
                ShoppingList.owner_id == user.id,
                ShoppingList.id.in_(member_list_ids_stmt),
            ),
            ShoppingList.archived_at.is_(None),
        ]

        if status:
            conditions.append(ShoppingList.status == status)

        count_stmt = select(func.count()).select_from(ShoppingList).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar() or 0)

        lists_stmt = (
            select(ShoppingList)
            .options(
                selectinload(ShoppingList.items),
                selectinload(ShoppingList.members),
            )
            .where(*conditions)
            .order_by(ShoppingList.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        lists_result = await self.db.execute(lists_stmt)
        shopping_lists = list(lists_result.scalars().all())

        items = []
        for sl in shopping_lists:
            active_items = [i for i in sl.items if i.archived_at is None]
            item_count = len(active_items)
            checked_count = sum(1 for i in active_items if i.is_checked)

            member_count = 0
            if sl.is_shared:
                member_count = len([m for m in sl.members if m.archived_at is None])

            is_owner = sl.owner_id == user.id
            membership = next(
                (m for m in sl.members if m.user_id == user.id and not m.archived_at),
                None,
            )
            role = membership.role if membership else ("owner" if is_owner else None)

            is_default = (
                user.default_shopping_list_id is not None
                and str(sl.id) == str(user.default_shopping_list_id)
            )

            items.append(
                ListShoppingLists.ShoppingListItem(
                    id=str(sl.id),
                    name=sl.name,
                    status=sl.status,
                    meal_event_id=(
                        str(sl.meal_event_id) if sl.meal_event_id else None
                    ),
                    item_count=item_count,
                    checked_count=checked_count,
                    is_shared=sl.is_shared,
                    is_default=is_default,
                    member_count=member_count,
                    role=role,
                    owner_id=str(sl.owner_id),
                    default_deadline=sl.default_deadline,
                    created_at=sl.created_at,
                    updated_at=sl.updated_at,
                )
            )

        return success(
            data=ListShoppingLists.Response(
                items=items, total=total, limit=limit, offset=offset
            )
        )

    class ShoppingListItem(BaseModel):
        id: str
        name: str | None = None
        status: str
        meal_event_id: str | None = None
        item_count: int = 0
        checked_count: int = 0
        is_shared: bool = False
        is_default: bool = False
        member_count: int = 0
        role: str | None = None  # owner, editor, viewer
        owner_id: str
        default_deadline: datetime | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        items: list["ListShoppingLists.ShoppingListItem"]
        total: int
        limit: int
        offset: int
