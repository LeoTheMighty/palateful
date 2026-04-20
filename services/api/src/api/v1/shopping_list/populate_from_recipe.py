"""Add recipe ingredients to an existing shopping list endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser


class PopulateFromRecipe(Endpoint):
    """Add all ingredients from a recipe to an existing shopping list."""

    def execute(self, list_id: str, params: "PopulateFromRecipe.Params"):
        """
        Add all non-archived ingredients from a recipe to a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Parameters including recipe_id

        Returns:
            Summary of items added and skipped
        """
        user = self.user

        # Find recipe
        recipe = self.database.find_by(Recipe, id=params.recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{params.recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Verify user can view recipe
        recipe_membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id,
        )
        if not recipe_membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        # Find shopping list
        shopping_list = self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        # Verify user can edit shopping list
        is_owner = shopping_list.owner_id == user.id
        list_membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=user.id
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

        # Build deduplication set: skip items already added from the same recipe+ingredient
        existing_keys = {
            (item.ingredient_id, item.recipe_id)
            for item in shopping_list.items
            if item.archived_at is None
        }

        added_items = []
        items_skipped = 0

        for recipe_ingredient in recipe.ingredients:
            if recipe_ingredient.archived_at is not None:
                continue

            ingredient = recipe_ingredient.ingredient
            if ingredient is None:
                continue

            if (ingredient.id, recipe.id) in existing_keys:
                items_skipped += 1
                continue

            raw_qty = recipe_ingredient.quantity_display
            if raw_qty is not None and params.scale_factor != 1.0:
                scaled = Decimal(str(raw_qty)) * Decimal(str(params.scale_factor))
                raw_qty = scaled.quantize(Decimal("0.01")).normalize()

            item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=ingredient.canonical_name,
                quantity=raw_qty,
                unit=recipe_ingredient.unit_display,
                category=None,
                ingredient_id=ingredient.id,
                recipe_id=recipe.id,
                added_by_user_id=user.id,
            )
            self.database.create(item)
            self.database.db.refresh(item)

            added_items.append(
                PopulateFromRecipe.ItemResponse(
                    id=str(item.id),
                    name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    is_checked=item.is_checked,
                    category=item.category,
                    ingredient_id=str(item.ingredient_id) if item.ingredient_id else None,
                    recipe_id=str(item.recipe_id) if item.recipe_id else None,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )

        self.database.db.commit()

        return success(
            data=PopulateFromRecipe.Response(
                items_added=len(added_items),
                items_skipped=items_skipped,
                items=added_items,
            )
        )

    class Params(BaseModel):
        recipe_id: str
        scale_factor: float = 1.0

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: Decimal | None = None
        unit: str | None = None
        is_checked: bool
        category: str | None = None
        ingredient_id: str | None = None
        recipe_id: str | None = None
        created_at: datetime
        updated_at: datetime

    class Response(BaseModel):
        items_added: int
        items_skipped: int
        items: list["PopulateFromRecipe.ItemResponse"] = []
