"""List shopping lists endpoint."""

from datetime import datetime

from pydantic import BaseModel
from utils.api.endpoint import Endpoint, success
from utils.models.shopping_list import ShoppingList
from utils.models.user import User


class ListShoppingLists(Endpoint):
    """List shopping lists for the current user."""

    def execute(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ):
        """
        List shopping lists for the current user.

        Args:
            limit: Maximum number of results
            offset: Pagination offset
            status: Filter by status

        Returns:
            Paginated list of shopping lists
        """
        user: User = self.user

        # Build query
        query = (
            self.db.query(ShoppingList)
            .filter(ShoppingList.owner_id == user.id)
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
        created_at: datetime

    class Response(BaseModel):
        items: list["ListShoppingLists.ShoppingListItem"]
        total: int
        limit: int
        offset: int
