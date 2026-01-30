"""Get recipe endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.user import User


class GetRecipe(Endpoint):
    """Get recipe details by ID."""

    def execute(self, recipe_id: str):
        """
        Get recipe details including ingredients.

        Args:
            recipe_id: The recipe's ID

        Returns:
            Recipe details with ingredients
        """
        user: User = self.user

        # Get recipe
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND
            )

        # Check access via recipe book
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id
        )
        if not membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED
            )

        # Get ingredients with ingredient details
        recipe_ingredients = (
            self.db.query(RecipeIngredient, Ingredient)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .filter(RecipeIngredient.recipe_id == recipe_id)
            .order_by(RecipeIngredient.order_index)
            .all()
        )

        ingredient_responses = [
            GetRecipe.IngredientResponse(
                id=ri.id,
                ingredient=GetRecipe.IngredientSummary(
                    id=ing.id,
                    canonical_name=ing.canonical_name,
                    category=ing.category
                ),
                quantity_display=ri.quantity_display,
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
            data=GetRecipe.Response(
                id=recipe.id,
                name=recipe.name,
                description=recipe.description,
                instructions=recipe.instructions,
                servings=recipe.servings,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                image_url=recipe.image_url,
                source_url=recipe.source_url,
                ingredients=ingredient_responses,
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
        ingredient: "GetRecipe.IngredientSummary"
        quantity_display: Decimal
        unit_display: str
        quantity_normalized: Decimal | None = None
        unit_normalized: str | None = None
        notes: str | None = None
        is_optional: bool = False
        order_index: int = 0

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
        ingredients: list["GetRecipe.IngredientResponse"] = []
        created_at: datetime
        updated_at: datetime
