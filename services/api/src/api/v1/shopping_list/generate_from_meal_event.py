"""Generate shopping list from meal event endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.pantry_ingredient import PantryIngredient
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.user import User


class GenerateFromMealEvent(Endpoint):
    """Generate a shopping list from a meal event's recipe."""

    def execute(self, event_id: str, params: "GenerateFromMealEvent.Params"):
        """
        Generate a shopping list from a meal event's recipe.

        Args:
            event_id: The meal event's ID
            params: Generation parameters

        Returns:
            Generated shopping list data
        """
        user: User = self.user

        # Find meal event
        meal_event = self.database.find_by(MealEvent, id=event_id)
        if not meal_event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        # Check access
        is_owner = meal_event.owner_id == user.id
        participant = self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=user.id
        )
        if not is_owner and not participant:
            raise APIException(
                status_code=403,
                detail="You don't have access to this meal event",
                code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
            )

        # Check if recipe exists
        if not meal_event.recipe:
            raise APIException(
                status_code=400,
                detail="Meal event has no recipe to generate shopping list from",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Check if shopping list already exists
        if meal_event.shopping_list:
            raise APIException(
                status_code=400,
                detail="Shopping list already exists for this meal event",
                code=ErrorCode.INVALID_REQUEST,
            )

        # Get pantry ingredients if checking pantry
        pantry_ingredients = {}
        if params.check_pantry and meal_event.pantry_id:
            pantry_items = (
                self.db.query(PantryIngredient)
                .filter(PantryIngredient.pantry_id == meal_event.pantry_id)
                .filter(PantryIngredient.archived_at.is_(None))
                .all()
            )
            for pi in pantry_items:
                pantry_ingredients[pi.ingredient_id] = pi

        # Create shopping list
        shopping_list = ShoppingList(
            name=f"Shopping for {meal_event.title}",
            meal_event_id=meal_event.id,
            pantry_id=meal_event.pantry_id,
            owner_id=user.id,
        )
        self.database.create(shopping_list)
        self.database.db.refresh(shopping_list)

        # Add recipe ingredients to shopping list
        item_responses = []
        for recipe_ing in meal_event.recipe.ingredients:
            if recipe_ing.archived_at is not None:
                continue

            # Check pantry for existing quantity
            already_have = None
            need_quantity = recipe_ing.quantity_display
            if params.check_pantry and recipe_ing.ingredient_id in pantry_ingredients:
                pantry_ing = pantry_ingredients[recipe_ing.ingredient_id]
                already_have = pantry_ing.quantity_display
                # Calculate what's still needed
                if pantry_ing.unit_display == recipe_ing.unit_display:
                    remaining = recipe_ing.quantity_display - pantry_ing.quantity_display
                    if remaining <= 0:
                        continue  # Don't add if we have enough
                    need_quantity = remaining

            item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=recipe_ing.ingredient.canonical_name,
                quantity=need_quantity,
                unit=recipe_ing.unit_display,
                category=recipe_ing.ingredient.category,
                ingredient_id=recipe_ing.ingredient_id,
                recipe_id=meal_event.recipe.id,
                already_have_quantity=already_have,
            )
            self.database.create(item)
            self.database.db.refresh(item)

            item_responses.append(
                GenerateFromMealEvent.ItemResponse(
                    id=str(item.id),
                    name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    is_checked=item.is_checked,
                    category=item.category,
                    ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
                    recipe_id=str(item.recipe_id) if item.recipe_id else None,
                    already_have_quantity=item.already_have_quantity,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )

        return success(
            data=GenerateFromMealEvent.Response(
                id=str(shopping_list.id),
                name=shopping_list.name,
                status=shopping_list.status,
                meal_event_id=str(shopping_list.meal_event_id),
                pantry_id=(
                    str(shopping_list.pantry_id) if shopping_list.pantry_id else None
                ),
                owner_id=str(shopping_list.owner_id),
                items=item_responses,
                created_at=shopping_list.created_at,
                updated_at=shopping_list.updated_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        check_pantry: bool = True

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None
        already_have_quantity: Decimal | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        id: str
        name: str | None = None
        status: str
        meal_event_id: str | None = None
        pantry_id: str | None = None
        owner_id: str
        items: list["GenerateFromMealEvent.ItemResponse"] = []
        created_at: datetime
        updated_at: datetime
