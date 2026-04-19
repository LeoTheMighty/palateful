"""POST /v1/meals/{meal_id}/add-to-shopping-list — Meal expansion path.

Sister endpoint to PopulateFromRecipe — instead of expanding one recipe,
expands every component of a Meal via `aggregate_meal_ingredients`
(mcal-2). Items land with `meal_event_id=NULL` (no calendar event) and
`source_meal_id=meal.id` for descriptive provenance.

Auth: read-membership on the Meal's recipe_book + write-membership on
the target shopping list.
"""

from datetime import datetime
from decimal import Decimal

from api.v1.meal._access import require_meal_read
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.services.meal_service import aggregate_meal_ingredients


class AddMealToShoppingList(Endpoint):
    """Expand a Meal's aggregate ingredients into a shopping list."""

    def execute(self, meal_id: str, params: "AddMealToShoppingList.Params"):
        user = self.user

        meal = require_meal_read(self.database.db, meal_id, user)
        if meal.archived_at is not None:
            raise APIException(
                status_code=404,
                detail="Meal not found",
                code=ErrorCode.MEAL_NOT_FOUND,
            )

        shopping_list = self.database.find_by(
            ShoppingList, id=params.shopping_list_id
        )
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{params.shopping_list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        is_owner = shopping_list.owner_id == user.id
        list_membership = self.database.find_by(
            ShoppingListUser,
            shopping_list_id=params.shopping_list_id,
            user_id=user.id,
        )
        can_edit = is_owner or (
            list_membership
            and list_membership.role in ("owner", "editor")
            and not list_membership.archived_at
        )
        if not can_edit:
            raise APIException(
                status_code=403,
                detail="You don't have permission to add items to this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Existing-keys dedupe: same ingredient_id + same source_meal_id
        # already on the list → skip. This makes a re-tap idempotent
        # without scanning per-event keys (the per-event populate path
        # uses meal_event_id; this endpoint uses source_meal_id).
        existing_keys = {
            (item.ingredient_id, item.source_meal_id)
            for item in shopping_list.items
            if item.archived_at is None
        }

        aggregates = aggregate_meal_ingredients(meal, self.database.db)

        added_items = []
        items_skipped = 0
        for agg in aggregates:
            if (agg.ingredient_id, meal.id) in existing_keys:
                items_skipped += 1
                continue

            quantity = (
                agg.summed_quantity.quantize(Decimal("0.01")).normalize()
                if agg.summed_quantity is not None
                else None
            )

            item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=agg.ingredient_name,
                quantity=quantity,
                unit=agg.normalized_unit,
                category=agg.category,
                ingredient_id=agg.ingredient_id,
                # Meal expansion has no single canonical recipe_id;
                # provenance lives on source_meal_id instead.
                recipe_id=None,
                meal_event_id=None,
                source_meal_id=meal.id,
                added_by_user_id=user.id,
            )
            self.database.create(item)
            self.database.db.refresh(item)

            added_items.append(
                AddMealToShoppingList.ItemResponse(
                    id=str(item.id),
                    name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    is_checked=item.is_checked,
                    category=item.category,
                    ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
                    source_meal_id=str(item.source_meal_id) if item.source_meal_id else None,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )

        self.database.db.commit()

        return success(
            data=AddMealToShoppingList.Response(
                items_added=len(added_items),
                items_skipped=items_skipped,
                items=added_items,
                meal_summary=AddMealToShoppingList.MealSummary(
                    id=str(meal.id),
                    name=meal.name,
                    component_count=len(meal.components),
                ),
            )
        )

    class Params(BaseModel):
        shopping_list_id: str

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        category: str | None = None
        ingredient_id: str | None = None
        source_meal_id: str | None = None
        created_at: datetime
        updated_at: datetime

    class MealSummary(BaseModel):
        id: str
        name: str
        component_count: int

    class Response(BaseModel):
        items_added: int
        items_skipped: int
        items: list["AddMealToShoppingList.ItemResponse"] = []
        meal_summary: "AddMealToShoppingList.MealSummary"
