"""Create recipe endpoint."""

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


class CreateRecipe(Endpoint):
    """Create a new recipe."""

    def execute(self, book_id: str, params: "CreateRecipe.Params"):
        """
        Create a new recipe in a recipe book.

        Args:
            book_id: The recipe book's ID
            params: Recipe creation parameters

        Returns:
            Created recipe data
        """
        user: User = self.user

        # Check access - must be owner or editor
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=book_id
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to add recipes to this book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED
            )

        # Verify recipe book exists
        recipe_book = self.database.find_by(RecipeBook, id=book_id)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail=f"Recipe book with ID '{book_id}' not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND
            )

        # Create recipe
        recipe = Recipe(
            name=params.name,
            description=params.description,
            instructions=params.instructions,
            servings=params.servings,
            prep_time=params.prep_time,
            cook_time=params.cook_time,
            image_url=params.image_url,
            source_url=params.source_url,
            recipe_book_id=book_id
        )
        self.database.create(recipe)
        self.database.db.refresh(recipe)

        # Create recipe ingredients
        ingredient_responses = []
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
                # If normalization fails, use display values
                quantity_normalized = ing_input.quantity
                unit_normalized = ing_input.unit

            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
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

            ingredient_responses.append(
                CreateRecipe.IngredientResponse(
                    id=recipe_ingredient.id,
                    ingredient=CreateRecipe.IngredientSummary(
                        id=ingredient.id,
                        canonical_name=ingredient.canonical_name,
                        category=ingredient.category
                    ),
                    quantity_display=recipe_ingredient.quantity_display,
                    unit_display=recipe_ingredient.unit_display,
                    notes=recipe_ingredient.notes,
                    is_optional=recipe_ingredient.is_optional,
                    order_index=recipe_ingredient.order_index
                )
            )

        return success(
            data=CreateRecipe.Response(
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
            ),
            status=201
        )

    class IngredientInput(BaseModel):
        ingredient_id: str
        quantity: Decimal
        unit: str
        notes: Optional[str] = None
        is_optional: bool = False

    class Params(BaseModel):
        name: str
        description: Optional[str] = None
        instructions: Optional[str] = None
        servings: int = 1
        prep_time: Optional[int] = None
        cook_time: Optional[int] = None
        image_url: Optional[str] = None
        source_url: Optional[str] = None
        ingredients: list["CreateRecipe.IngredientInput"] = []

    class IngredientSummary(BaseModel):
        id: str
        canonical_name: str
        category: Optional[str] = None

    class IngredientResponse(BaseModel):
        id: str
        ingredient: "CreateRecipe.IngredientSummary"
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
        ingredients: list["CreateRecipe.IngredientResponse"] = []
        created_at: datetime
        updated_at: datetime
