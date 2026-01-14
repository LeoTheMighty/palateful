"""Update recipe endpoint."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional

from utils.api.endpoint import Endpoint, APIException, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.ingredient import Ingredient
from utils.models.user import User
from utils.services.units.conversion import normalize_quantity


class UpdateRecipe(Endpoint):
    """Update a recipe."""

    def execute(self, recipe_id: str, params: "UpdateRecipe.Params"):
        """
        Update a recipe.

        Args:
            recipe_id: The recipe's ID
            params: Update parameters

        Returns:
            Updated recipe data
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

        # Check access - must be owner or editor
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to edit this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED
            )

        # Build update dict
        updates = {}
        if params.name is not None:
            updates["name"] = params.name
        if params.description is not None:
            updates["description"] = params.description
        if params.instructions is not None:
            updates["instructions"] = params.instructions
        if params.servings is not None:
            updates["servings"] = params.servings
        if params.prep_time is not None:
            updates["prep_time"] = params.prep_time
        if params.cook_time is not None:
            updates["cook_time"] = params.cook_time
        if params.image_url is not None:
            updates["image_url"] = params.image_url
        if params.source_url is not None:
            updates["source_url"] = params.source_url

        # Update recipe if there are changes
        if updates:
            self.database.update(recipe, **updates)

        # Update ingredients if provided
        if params.ingredients is not None:
            # Delete existing ingredients
            existing = self.database.where(
                RecipeIngredient,
                recipe_id=recipe_id
            ).all()
            for ri in existing:
                self.database.delete(ri)

            # Create new ingredients
            for idx, ing_input in enumerate(params.ingredients):
                # Verify ingredient exists
                ingredient = self.database.find_by(Ingredient, id=ing_input.ingredient_id)
                if not ingredient:
                    raise APIException(
                        status_code=400,
                        detail=f"Ingredient with ID '{ing_input.ingredient_id}' not found",
                        code=ErrorCode.INGREDIENT_NOT_FOUND
                    )

                # Normalize quantity
                try:
                    normalized = normalize_quantity(
                        float(ing_input.quantity),
                        ing_input.unit
                    )
                    quantity_normalized = Decimal(str(normalized.quantity_normalized))
                    unit_normalized = normalized.unit_normalized
                except Exception:
                    quantity_normalized = ing_input.quantity
                    unit_normalized = ing_input.unit

                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe_id,
                    ingredient_id=ing_input.ingredient_id,
                    quantity_display=ing_input.quantity,
                    unit_display=ing_input.unit,
                    quantity_normalized=quantity_normalized,
                    unit_normalized=unit_normalized,
                    notes=ing_input.notes,
                    is_optional=ing_input.is_optional,
                    order_index=idx
                )
                self.database.create(recipe_ingredient)
                self.database.db.refresh(recipe_ingredient)

        # Fetch updated ingredients
        recipe_ingredients = (
            self.db.query(RecipeIngredient, Ingredient)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .filter(RecipeIngredient.recipe_id == recipe_id)
            .order_by(RecipeIngredient.order_index)
            .all()
        )

        ingredient_responses = [
            UpdateRecipe.IngredientResponse(
                id=ri.id,
                ingredient=UpdateRecipe.IngredientSummary(
                    id=ing.id,
                    canonical_name=ing.canonical_name,
                    category=ing.category
                ),
                quantity_display=ri.quantity_display,
                unit_display=ri.unit_display,
                notes=ri.notes,
                is_optional=ri.is_optional,
                order_index=ri.order_index
            )
            for ri, ing in recipe_ingredients
        ]

        return success(
            data=UpdateRecipe.Response(
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

    class IngredientInput(BaseModel):
        ingredient_id: str
        quantity: Decimal
        unit: str
        notes: Optional[str] = None
        is_optional: bool = False

    class Params(BaseModel):
        name: Optional[str] = None
        description: Optional[str] = None
        instructions: Optional[str] = None
        servings: Optional[int] = None
        prep_time: Optional[int] = None
        cook_time: Optional[int] = None
        image_url: Optional[str] = None
        source_url: Optional[str] = None
        ingredients: Optional[list["UpdateRecipe.IngredientInput"]] = None

    class IngredientSummary(BaseModel):
        id: str
        canonical_name: str
        category: Optional[str] = None

    class IngredientResponse(BaseModel):
        id: str
        ingredient: "UpdateRecipe.IngredientSummary"
        quantity_display: Decimal
        unit_display: str
        notes: Optional[str] = None
        is_optional: bool = False
        order_index: int = 0

    class Response(BaseModel):
        id: str
        name: str
        description: Optional[str] = None
        instructions: Optional[str] = None
        servings: int = 1
        prep_time: Optional[int] = None
        cook_time: Optional[int] = None
        image_url: Optional[str] = None
        source_url: Optional[str] = None
        ingredients: list["UpdateRecipe.IngredientResponse"] = []
        created_at: datetime
        updated_at: datetime
