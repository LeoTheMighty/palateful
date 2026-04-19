"""POST /v1/meal-events/{event_id}/add-to-shopping-list.

Per-event "Add to Shopping List" path. Replaces the now-deleted
PopulateFromCalendar's per-event behavior with a focused endpoint.

Branches by event linkage:
  * `recipe_id` set → expand the recipe via `populate_from_recipe` parity
    (single-recipe ingredients, dedupe key includes meal_event_id).
  * `meal_id` set → expand via `aggregate_meal_ingredients` (mcal-2),
    sum-within-meal dedupe.
  * neither set (free-text event) → 422; nothing to expand.

Items get `meal_event_id=<event.id>` so per-event dedupe stays separate
from the shop-without-scheduling path.
"""

from datetime import datetime
from decimal import Decimal

from api.v1.calendar.dependencies import require_calendar_access
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.services.meal_service import aggregate_meal_ingredients


class AddMealEventToShoppingList(Endpoint):
    """Append a single calendar event's ingredients to a shopping list."""

    def execute(
        self,
        event_id: str,
        params: "AddMealEventToShoppingList.Params",
    ):
        user = self.user

        event = self.database.find_by(MealEvent, id=event_id)
        if not event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        # Calendar membership gates the read on the event.
        require_calendar_access(str(event.calendar_id), user, self.database)

        if not event.recipe_id and not event.meal_id:
            raise APIException(
                status_code=422,
                detail="Free-text events have no ingredients to add",
                code=ErrorCode.VALIDATION_ERROR,
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

        # Re-tap dedupe — same (ingredient_id, meal_event_id) already on
        # the list = skip.
        existing_keys = {
            (item.ingredient_id, item.meal_event_id)
            for item in shopping_list.items
            if item.archived_at is None
        }

        added_items: list[AddMealEventToShoppingList.ItemResponse] = []
        items_skipped = 0

        if event.meal_id is not None:
            aggregates = aggregate_meal_ingredients(event.meal, self.database.db)
            for agg in aggregates:
                if (agg.ingredient_id, event.id) in existing_keys:
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
                    recipe_id=None,
                    meal_event_id=event.id,
                    source_meal_id=event.meal_id,
                    added_by_user_id=user.id,
                )
                self.database.create(item)
                self.database.db.refresh(item)
                added_items.append(_to_item_response(item))
        else:
            # Recipe-linked event: expand via the recipe's RecipeIngredient
            # rows. Mirrors PopulateFromRecipe but keyed on the per-event
            # dedupe — `recipe_id` carried for downstream activity logging.
            recipe = event.recipe
            if recipe is None:
                raise APIException(
                    status_code=404,
                    detail="Linked recipe is no longer available",
                    code=ErrorCode.RECIPE_NOT_FOUND,
                )
            for recipe_ingredient in recipe.ingredients:
                if recipe_ingredient.archived_at is not None:
                    continue
                ingredient = recipe_ingredient.ingredient
                if ingredient is None:
                    continue
                if (ingredient.id, event.id) in existing_keys:
                    items_skipped += 1
                    continue
                item = ShoppingListItem(
                    shopping_list_id=shopping_list.id,
                    name=ingredient.canonical_name,
                    quantity=recipe_ingredient.quantity_display,
                    unit=recipe_ingredient.unit_display,
                    category=ingredient.category,
                    ingredient_id=ingredient.id,
                    recipe_id=recipe.id,
                    meal_event_id=event.id,
                    source_meal_id=None,
                    added_by_user_id=user.id,
                )
                self.database.create(item)
                self.database.db.refresh(item)
                added_items.append(_to_item_response(item))

        self.database.db.commit()

        return success(
            data=AddMealEventToShoppingList.Response(
                items_added=len(added_items),
                items_skipped=items_skipped,
                items=added_items,
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
        recipe_id: str | None = None
        meal_event_id: str | None = None
        source_meal_id: str | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        items_added: int
        items_skipped: int
        items: list["AddMealEventToShoppingList.ItemResponse"] = []


def _to_item_response(item) -> AddMealEventToShoppingList.ItemResponse:
    return AddMealEventToShoppingList.ItemResponse(
        id=str(item.id),
        name=item.name,
        quantity=item.quantity,
        unit=item.unit,
        is_checked=item.is_checked,
        category=item.category,
        ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
        recipe_id=str(item.recipe_id) if item.recipe_id else None,
        meal_event_id=str(item.meal_event_id) if item.meal_event_id else None,
        source_meal_id=str(item.source_meal_id) if item.source_meal_id else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
