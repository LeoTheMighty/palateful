"""Get recipe endpoint."""

from datetime import datetime
from decimal import Decimal

from api.v1.recipe._response import build_recipe_response
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class GetRecipe(Endpoint):
    """Get recipe details by ID."""

    def execute(self, recipe_id: str, debug: bool = False):
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

        return success(
            data=build_recipe_response(
                self.database,
                user,
                recipe,
                can_edit=membership.role in ("owner", "editor"),
                debug=debug,
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

    class DebugPayload(BaseModel):
        import_item_id: str
        status: str
        source_type: str
        source_reference: str | None = None
        source_url: str | None = None
        last_successful_stage: str | None = None
        error_code: str | None = None
        error_message: str | None = None
        raw_data: dict | None = None
        parsed_recipe: dict | None = None
        user_edits: dict | None = None

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
        primary_vibe: str | None = None
        secondary_vibe: str | None = None
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
        inferred_fields: list[str] = []
        debug: "GetRecipe.DebugPayload | None" = None
