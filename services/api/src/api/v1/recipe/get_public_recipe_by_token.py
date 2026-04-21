"""Get public recipe by share token (no auth required)."""

from api.v1.recipe.get_public_recipe import GetPublicRecipe
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.formatting import format_quantity
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_step import RecipeStep


class GetPublicRecipeByToken(Endpoint):
    """Get recipe by its public share token."""

    def execute(self, token: str):
        recipe = (
            self.db.query(Recipe)
            .filter(Recipe.share_token == token)
            .filter(Recipe.archived_at.is_(None))
            .first()
        )
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        recipe_book = self.database.find_by(RecipeBook, id=recipe.recipe_book_id)

        steps = self.database.where(
            RecipeStep, asc="step_number", recipe_id=recipe.id
        ).all()

        recipe_ingredients = (
            self.db.query(RecipeIngredient, Ingredient)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .filter(RecipeIngredient.recipe_id == recipe.id)
            .filter(RecipeIngredient.archived_at.is_(None))
            .order_by(RecipeIngredient.order_index)
            .all()
        )

        return success(
            data=GetPublicRecipe.Response(
                id=recipe.id,
                name=recipe.name,
                description=recipe.description,
                instructions=recipe.instructions,
                servings=recipe.servings,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                image_url=recipe.image_url,
                source_url=recipe.source_url,
                tags=recipe.tags or [],
                ingredients=[
                    GetPublicRecipe.IngredientResponse(
                        id=str(ri.ingredient_id),
                        ingredient=GetPublicRecipe.IngredientSummary(
                            id=ing.id,
                            canonical_name=ing.canonical_name,
                        ),
                        quantity_display=format_quantity(ri.quantity_display, ri.unit_display),
                        unit_display=ri.unit_display,
                        quantity_normalized=ri.quantity_normalized,
                        unit_normalized=ri.unit_normalized,
                        notes=ri.notes,
                        is_optional=ri.is_optional,
                        order_index=ri.order_index,
                    )
                    for ri, ing in recipe_ingredients
                ],
                steps=[
                    GetPublicRecipe.StepResponse(
                        id=str(s.id),
                        step_number=s.step_number,
                        instruction=s.instruction,
                        active_time_minutes=s.active_time_minutes,
                        timers=s.timers,
                        wait_time_minutes=s.wait_time_minutes,
                        wait_type=s.wait_type,
                        can_prep_ahead=s.can_prep_ahead,
                        is_optional=s.is_optional,
                    )
                    for s in steps
                ],
                recipe_book_name=recipe_book.name if recipe_book else "",
                created_at=recipe.created_at,
                updated_at=recipe.updated_at,
            )
        )
