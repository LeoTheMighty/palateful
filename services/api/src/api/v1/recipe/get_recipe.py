"""Get recipe endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.formatting import format_quantity
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_note import RecipeNote
from utils.models.recipe_step import RecipeStep
from utils.models.recipe_version import RecipeVersion
from utils.models.user import User
from utils.models.user_favorite import UserFavorite


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

        # Get recipe steps
        steps = self.database.where(
            RecipeStep,
            asc="step_number",
            recipe_id=recipe.id
        ).all()

        step_responses = [
            GetRecipe.StepResponse(
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
        recipe_ingredients = (
            self.db.query(RecipeIngredient, Ingredient)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .filter(RecipeIngredient.recipe_id == recipe_id)
            .order_by(RecipeIngredient.order_index)
            .all()
        )

        ingredient_responses = [
            GetRecipe.IngredientResponse(
                id=str(ri.ingredient_id),
                ingredient=GetRecipe.IngredientSummary(
                    id=str(ing.id),
                    canonical_name=ing.canonical_name,
                    category=ing.category
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

        # Check if user has favorited this recipe
        favorite = self.database.find_by(
            UserFavorite,
            user_id=user.id,
            recipe_id=recipe_id,
        )

        # Get version count
        version_count = self.database.where(
            RecipeVersion,
            recipe_id=recipe_id,
        ).count()

        # Get notes (active only, oldest first)
        notes = self.database.where(
            RecipeNote,
            recipe_id=recipe_id,
            asc="created_at",
        ).all()

        note_responses = [
            GetRecipe.NoteResponse(
                id=str(n.id),
                body=n.body,
                created_by=str(n.created_by) if n.created_by else None,
                created_at=n.created_at,
            )
            for n in notes
        ]

        return success(
            data=GetRecipe.Response(
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
                can_edit=membership.role in ("owner", "editor"),
                is_favorite=favorite is not None,
                ingredients=ingredient_responses,
                steps=step_responses,
                notes=note_responses,
                created_at=recipe.created_at,
                updated_at=recipe.updated_at,
                version_count=version_count,
                forked_from_recipe_id=str(recipe.forked_from_recipe_id) if recipe.forked_from_recipe_id else None,
                forked_from_book_id=str(recipe.forked_from_book_id) if recipe.forked_from_book_id else None,
                forked_from_recipe_name=recipe.forked_from_recipe_name,
                forked_from_book_name=recipe.forked_from_book_name,
            )
        )

    class IngredientSummary(BaseModel):
        id: str
        canonical_name: str
        category: str | None = None

    class IngredientResponse(BaseModel):
        id: str
        ingredient: "GetRecipe.IngredientSummary"
        quantity_display: str
        unit_display: str
        quantity_normalized: Decimal | None = None
        unit_normalized: str | None = None
        notes: str | None = None
        is_optional: bool = False
        order_index: int = 0

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

    class NoteResponse(BaseModel):
        id: str
        body: str
        created_by: str | None = None
        created_at: datetime

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
        can_edit: bool = False
        is_favorite: bool = False
        ingredients: list["GetRecipe.IngredientResponse"] = []
        steps: list["GetRecipe.StepResponse"] = []
        notes: list["GetRecipe.NoteResponse"] = []
        created_at: datetime
        updated_at: datetime
        version_count: int = 0
        forked_from_recipe_id: str | None = None
        forked_from_book_id: str | None = None
        forked_from_recipe_name: str | None = None
        forked_from_book_name: str | None = None
