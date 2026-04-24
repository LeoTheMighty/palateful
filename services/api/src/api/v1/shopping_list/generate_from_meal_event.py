"""Generate shopping list from meal event endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.recipe import Recipe
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.user import User


class GenerateFromMealEvent(AsyncEndpoint):
    """Generate a shopping list from a meal event's recipe."""

    async def execute(self, event_id: str, params: "GenerateFromMealEvent.Params"):
        """
        Generate a shopping list from a meal event's recipe.

        Args:
            event_id: The meal event's ID
            params: Generation parameters

        Returns:
            Generated shopping list data
        """
        user: User = self.user

        meal_event = await (
            self.database.where(MealEvent, id=event_id)
            .options(
                selectinload(MealEvent.recipe)
                .selectinload(Recipe.ingredients)
                .selectinload(RecipeIngredient.ingredient),
                selectinload(MealEvent.shopping_list),
            )
            .first()
        )
        if not meal_event:
            raise APIException(
                status_code=404,
                detail=f"Meal event with ID '{event_id}' not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )

        is_owner = meal_event.owner_id == user.id
        participant = await self.database.find_by(
            MealEventParticipant, meal_event_id=event_id, user_id=user.id
        )
        if not is_owner and not participant:
            raise APIException(
                status_code=403,
                detail="You don't have access to this meal event",
                code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
            )

        if not meal_event.recipe:
            raise APIException(
                status_code=400,
                detail="Meal event has no recipe to generate shopping list from",
                code=ErrorCode.INVALID_REQUEST,
            )

        if meal_event.shopping_list:
            raise APIException(
                status_code=400,
                detail="Shopping list already exists for this meal event",
                code=ErrorCode.INVALID_REQUEST,
            )

        shopping_list = ShoppingList(
            name=f"Shopping for {meal_event.title}",
            meal_event_id=meal_event.id,
            pantry_id=meal_event.pantry_id,
            owner_id=user.id,
        )
        await self.database.create(shopping_list)

        # Add recipe ingredients to shopping list. Pantry cross-check was
        # retired in epic-ingredients-string-simplification; every row
        # flows through regardless of pantry stock.
        item_responses = []
        for recipe_ing in meal_event.recipe.ingredients:
            if recipe_ing.archived_at is not None:
                continue

            item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=recipe_ing.ingredient.canonical_name,
                quantity=recipe_ing.quantity_display,
                unit=recipe_ing.unit_display,
                category=None,
                ingredient_id=recipe_ing.ingredient_id,
                recipe_id=meal_event.recipe.id,
                already_have_quantity=None,
            )
            await self.database.create(item)

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
        # extra="forbid" rejects the now-retired `check_pantry` flag
        # (retired in epic-ingredients-string-simplification). Keeps the
        # contract explicit for stale clients instead of silently 201.
        model_config = ConfigDict(extra="forbid")

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
