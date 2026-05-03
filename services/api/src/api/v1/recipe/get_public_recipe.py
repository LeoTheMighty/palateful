"""Get public recipe endpoint (no auth required)."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_serializer
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.formatting import format_quantity
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_step import RecipeStep


class GetPublicRecipe(AsyncEndpoint):
    """Get recipe details by ID if the recipe book is public."""

    async def execute(self, recipe_id: str):
        """
        Get recipe details for a publicly shared recipe.

        Args:
            recipe_id: The recipe's ID

        Returns:
            Recipe details with ingredients and recipe book name
        """
        # Get recipe
        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND
            )

        # Check that the recipe book is public
        recipe_book = await self.database.find_by(
            RecipeBook, id=recipe.recipe_book_id
        )
        if not recipe_book or not recipe_book.is_public:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND
            )

        # Get recipe steps
        steps = await self.database.where(
            RecipeStep,
            asc="step_number",
            recipe_id=recipe.id
        ).all()

        step_responses = [
            GetPublicRecipe.StepResponse(
                id=str(step.id),
                step_number=step.step_number,
                instruction=step.instruction,
                active_time_minutes=step.active_time_minutes,
                timers=step.timers,
                wait_time_minutes=step.wait_time_minutes,
                wait_type=step.wait_type,
                can_prep_ahead=step.can_prep_ahead,
                is_optional=step.is_optional
            )
            for step in steps
        ]

        # Get ingredients with ingredient details
        ri_result = await self.db.execute(
            select(RecipeIngredient, Ingredient)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .where(RecipeIngredient.recipe_id == recipe_id)
            .order_by(RecipeIngredient.order_index)
        )
        recipe_ingredients = list(ri_result.all())

        ingredient_responses = [
            GetPublicRecipe.IngredientResponse(
                id=str(ri.ingredient_id),
                ingredient=GetPublicRecipe.IngredientSummary(
                    id=str(ing.id),
                    canonical_name=ing.canonical_name,
                ),
                quantity_display=format_quantity(ri.quantity_display, ri.unit_display),
                unit_display=ri.unit_display,
                quantity_normalized=ri.quantity_normalized,
                unit_normalized=ri.unit_normalized,
                notes=ri.notes,
                is_optional=ri.is_optional,
                order_index=ri.order_index
            )
            for ri, ing in recipe_ingredients
        ]

        return success(
            data=GetPublicRecipe.Response(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                instructions=recipe.instructions,
                servings=recipe.servings,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                image_url=recipe.image_url,
                source_url=recipe.source_url,
                tags=recipe.tags or [],
                ingredients=ingredient_responses,
                steps=step_responses,
                recipe_book_name=recipe_book.name,
                created_at=recipe.created_at,
                updated_at=recipe.updated_at
            )
        )

    class IngredientSummary(BaseModel):
        id: str
        canonical_name: str
        category: str | None = None

    class IngredientResponse(BaseModel):
        id: str
        ingredient: "GetPublicRecipe.IngredientSummary"
        quantity_display: str
        unit_display: str
        quantity_normalized: Decimal | None = None
        unit_normalized: str | None = None
        notes: str | None = None
        is_optional: bool = False
        order_index: int = 0

        # ifh-2: same Decimal-as-string fix as the GetRecipe sibling
        # (see commit a5c8438 for the cart-bug root cause this prevents).
        @field_serializer("quantity_normalized")
        def _quantity_normalized_to_float(
            self, value: Decimal | None
        ) -> float | None:
            return float(value) if value is not None else None

    class StepResponse(BaseModel):
        id: str
        step_number: int
        instruction: str
        active_time_minutes: int | None = None
        timers: list[dict] | None = None
        wait_time_minutes: int | None = None
        wait_type: str | None = None
        can_prep_ahead: bool = False
        is_optional: bool = False

    class Response(BaseModel):
        id: str
        name: str
        description: str | None = None
        instructions: str | None = None
        servings: int = 1
        prep_time: int | None = None
        cook_time: int | None = None
        image_url: str | None = None
        source_url: str | None = None
        tags: list[str] = []
        ingredients: list["GetPublicRecipe.IngredientResponse"] = []
        steps: list["GetPublicRecipe.StepResponse"] = []
        recipe_book_name: str
        created_at: datetime
        updated_at: datetime
