"""Populate shopping list from calendar meal events endpoint."""

from datetime import date, datetime, timedelta

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User

from .utils.deadline import calculate_item_due_date


class PopulateFromCalendar(Endpoint):
    """Populate a shopping list with ingredients from upcoming meal events."""

    def execute(self, list_id: str, params: "PopulateFromCalendar.Params"):
        """
        Populate a shopping list from calendar meal events.

        This endpoint:
        1. Finds meal events in the date range
        2. Extracts ingredients from each meal's recipe
        3. Optionally checks pantry for existing items
        4. Creates shopping list items with proper due dates
        5. Groups/aggregates similar ingredients

        Args:
            list_id: The shopping list's ID
            params: Population parameters

        Returns:
            Summary of items added
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

        # Check access - owner or member with edit permission
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
                detail="You don't have permission to modify this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Calculate date range
        start_date = params.start_date or date.today()
        if params.end_date:
            end_date = params.end_date
        else:
            lookahead = shopping_list.calendar_lookahead_days or 7
            end_date = start_date + timedelta(days=lookahead)

        # Convert to datetime for query
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Query meal events in range
        query = (
            self.db.query(MealEvent)
            .filter(MealEvent.owner_id == user.id)
            .filter(MealEvent.archived_at.is_(None))
            .filter(MealEvent.scheduled_at >= start_datetime)
            .filter(MealEvent.scheduled_at <= end_datetime)
            .filter(MealEvent.status.in_(["planned", "shopping", "prepping"]))
        )

        # Filter by specific meal event IDs if provided
        if params.include_meal_event_ids:
            query = query.filter(MealEvent.id.in_(params.include_meal_event_ids))

        meal_events = query.order_by(MealEvent.scheduled_at).all()

        # Track what we're adding
        items_added = 0
        items_skipped = 0
        meal_events_included = []
        added_items = []

        # Get pantry ingredients if checking pantry
        pantry_ingredients = {}
        if params.check_pantry and shopping_list.pantry_id:
            pantry_items = (
                self.db.query(PantryIngredient)
                .filter(PantryIngredient.pantry_id == shopping_list.pantry_id)
                .filter(PantryIngredient.archived_at.is_(None))
                .all()
            )
            for pi in pantry_items:
                pantry_ingredients[pi.ingredient_id] = pi.quantity

        # Get existing items in the list to avoid duplicates
        existing_items = {}
        for item in shopping_list.items:
            if item.archived_at is None:
                key = (item.ingredient_id, item.meal_event_id)
                existing_items[key] = item

        # Process each meal event
        for meal_event in meal_events:
            if not meal_event.recipe:
                continue

            recipe = meal_event.recipe
            meal_events_included.append({
                "id": str(meal_event.id),
                "title": meal_event.title,
                "scheduled_at": meal_event.scheduled_at.isoformat(),
            })

            # Process each ingredient in the recipe
            for recipe_ingredient in recipe.ingredients:
                if recipe_ingredient.archived_at:
                    continue

                ingredient = recipe_ingredient.ingredient
                if not ingredient:
                    continue

                # Check if already in list for this meal event
                key = (ingredient.id, meal_event.id)
                if key in existing_items:
                    items_skipped += 1
                    continue

                # Calculate needed quantity
                needed_quantity = recipe_ingredient.quantity

                # Check pantry
                already_have = None
                if ingredient.id in pantry_ingredients:
                    pantry_qty = pantry_ingredients[ingredient.id]
                    if pantry_qty and needed_quantity:
                        already_have = min(pantry_qty, needed_quantity)
                        # Don't add if we have enough
                        if pantry_qty >= needed_quantity:
                            items_skipped += 1
                            continue

                # Create shopping list item
                item = ShoppingListItem(
                    shopping_list_id=shopping_list.id,
                    name=ingredient.name,
                    quantity=needed_quantity,
                    unit=recipe_ingredient.unit,
                    category=ingredient.category,
                    ingredient_id=ingredient.id,
                    recipe_id=recipe.id,
                    meal_event_id=meal_event.id,
                    already_have_quantity=already_have,
                    added_by_user_id=user.id,
                )

                # Calculate due date
                due_at, due_reason = calculate_item_due_date(
                    item, meal_event=meal_event, shopping_list=shopping_list
                )
                item.due_at = due_at
                item.due_reason = due_reason

                self.database.create(item)
                items_added += 1
                added_items.append({
                    "id": str(item.id),
                    "name": item.name,
                    "quantity": float(item.quantity) if item.quantity else None,
                    "unit": item.unit,
                    "meal_event_id": str(meal_event.id),
                    "due_at": item.due_at.isoformat() if item.due_at else None,
                })

        self.database.db.commit()

        return success(
            data=PopulateFromCalendar.Response(
                items_added=items_added,
                items_skipped=items_skipped,
                meal_events_included=len(meal_events_included),
                meal_events=meal_events_included,
                items=added_items,
            )
        )

    class Params(BaseModel):
        start_date: date | None = None  # Defaults to today
        end_date: date | None = None  # Defaults to start + lookahead_days
        check_pantry: bool = True  # Whether to check pantry for existing items
        include_meal_event_ids: list[str] | None = None  # Filter to specific events

    class Response(BaseModel):
        items_added: int
        items_skipped: int
        meal_events_included: int
        meal_events: list[dict]
        items: list[dict]
