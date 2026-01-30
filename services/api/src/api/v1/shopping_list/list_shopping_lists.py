"""List shopping lists endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import or_
from utils.api.endpoint import Endpoint, success
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class ListShoppingLists(Endpoint):
    """List shopping lists for the current user (owned and shared)."""

    def execute(
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

        # Get IDs of lists where user is a member
        member_list_ids = (
            self.db.query(ShoppingListUser.shopping_list_id)
            .filter(ShoppingListUser.user_id == user.id)
            .filter(ShoppingListUser.archived_at.is_(None))
            .subquery()
        )

        # Build query: owned OR member
        query = (
            self.db.query(ShoppingList)
            .filter(
                or_(
                    ShoppingList.owner_id == user.id,
                    ShoppingList.id.in_(member_list_ids),
                )
            )
            .filter(ShoppingList.archived_at.is_(None))
        )

        # Apply status filter
        if status:
            query = query.filter(ShoppingList.status == status)

        # Get total count
        total = query.count()

        # Apply ordering and pagination
        shopping_lists = (
            query.order_by(ShoppingList.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = []
        for sl in shopping_lists:
            # Count items and checked items
            active_items = [i for i in sl.items if i.archived_at is None]
            item_count = len(active_items)
            checked_count = sum(1 for i in active_items if i.is_checked)

            # Get member count
            member_count = 0
            if sl.is_shared:
                member_count = len([m for m in sl.members if m.archived_at is None])

            # Determine user's role
            is_owner = sl.owner_id == user.id
            membership = next(
                (m for m in sl.members if m.user_id == user.id and not m.archived_at),
                None,
            )
            role = membership.role if membership else ("owner" if is_owner else None)

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
                    member_count=member_count,
                    role=role,
                    owner_id=str(sl.owner_id),
                    default_deadline=sl.default_deadline,
                    created_at=sl.created_at,
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
        member_count: int = 0
        role: str | None = None  # owner, editor, viewer
        owner_id: str
        default_deadline: datetime | None = None
        created_at: datetime

    class Response(BaseModel):
        items: list["ListShoppingLists.ShoppingListItem"]
        total: int
        limit: int
        offset: int
