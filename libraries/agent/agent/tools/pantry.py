"""Pantry tool for accessing user's pantry items."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agent.tools.base import BaseTool, ToolResult


class GetPantryTool(BaseTool):
    """Tool to get the user's current pantry items."""

    @property
    def name(self) -> str:
        return "get_pantry"

    @property
    def description(self) -> str:
        return """Get the user's current pantry items. Returns a list of ingredients
        they have available, including quantities and expiration dates. Use this to
        understand what ingredients the user has for meal planning."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "include_expired": {
                    "type": "boolean",
                    "description": "Whether to include expired items",
                    "default": False,
                },
                "expiring_within_days": {
                    "type": "integer",
                    "description": "Only return items expiring within N days (optional)",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by ingredient category (e.g., 'produce', 'protein')",
                },
            },
            "required": [],
        }

    def execute(
        self,
        db: Session,
        user_id: str,
        include_expired: bool = False,
        expiring_within_days: int | None = None,
        category: str | None = None,
    ) -> ToolResult:
        """Get pantry items for the user."""
        from utils.models import PantryUser, PantryIngredient

        try:
            # Get user's pantry memberships
            pantry_query = select(PantryUser).where(PantryUser.user_id == user_id)
            pantry_result = db.execute(pantry_query)
            pantry_users = pantry_result.scalars().all()

            if not pantry_users:
                return ToolResult(
                    success=True,
                    data={
                        "items": [],
                        "message": "User has no pantry set up yet.",
                    },
                )

            # Get pantry IDs
            pantry_ids = [pu.pantry_id for pu in pantry_users]

            # Build query for pantry ingredients
            query = (
                select(PantryIngredient)
                .options(selectinload(PantryIngredient.ingredient))
                .where(PantryIngredient.pantry_id.in_(pantry_ids))
                .where(PantryIngredient.archived_at.is_(None))
            )

            # Filter expired items
            if not include_expired:
                query = query.where(
                    (PantryIngredient.expires_at.is_(None))
                    | (PantryIngredient.expires_at > datetime.utcnow())
                )

            # Filter by expiring within N days
            if expiring_within_days is not None:
                expiry_threshold = datetime.utcnow() + timedelta(days=expiring_within_days)
                query = query.where(
                    (PantryIngredient.expires_at.is_not(None))
                    & (PantryIngredient.expires_at <= expiry_threshold)
                )

            result = db.execute(query)
            pantry_items = result.scalars().all()

            # Format items for response
            items = []
            for item in pantry_items:
                ingredient = item.ingredient
                if category and ingredient.category != category:
                    continue

                item_data = {
                    "ingredient_name": ingredient.canonical_name,
                    "category": ingredient.category,
                    "quantity": item.quantity,
                    "unit": item.unit,
                }

                if item.expires_at:
                    item_data["expires_at"] = item.expires_at.isoformat()
                    days_until = (item.expires_at - datetime.utcnow()).days
                    item_data["days_until_expiry"] = max(0, days_until)
                    if days_until <= 3:
                        item_data["expiring_soon"] = True

                items.append(item_data)

            # Sort by expiration (soonest first)
            items.sort(key=lambda x: x.get("days_until_expiry", 999))

            return ToolResult(
                success=True,
                data={
                    "items": items,
                    "total_count": len(items),
                    "expiring_soon_count": sum(1 for i in items if i.get("expiring_soon")),
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))
