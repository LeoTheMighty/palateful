"""Update recipe endpoint."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import func
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
from utils.services.units.conversion import normalize_quantity

# Fields that trigger a new version snapshot
VERSION_TRIGGERING_FIELDS = {"name", "instructions", "ingredients", "steps"}


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

        # Determine which version-triggering fields are actually changing
        changed_fields = []
        if params.name is not None and params.name != recipe.name:
            changed_fields.append("name")
        if params.instructions is not None and params.instructions != recipe.instructions:
            changed_fields.append("instructions")
        if params.ingredients is not None:
            changed_fields.append("ingredients")
        if params.steps is not None:
            changed_fields.append("steps")

        # Create version snapshot BEFORE applying updates
        if changed_fields:
            self._create_version_snapshot(recipe, recipe_id, changed_fields, user)

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
        if params.tags is not None:
            updates["tags"] = params.tags

        # Capture old values for embedding diff check
        old_name, old_desc, old_tags = recipe.name, recipe.description, recipe.tags

        # Update recipe if there are changes
        if updates:
            self.database.update(recipe, **updates)

        # Regenerate embedding only when searchable content actually changed
        embedding_fields = {"name", "description", "tags"}
        if updates and embedding_fields.intersection(updates.keys()):
            content_changed = (
                recipe.name != old_name
                or recipe.description != old_desc
                or recipe.tags != old_tags
            )
            if content_changed:
                from api.v1.search.generate_recipe_embedding import generate_recipe_embedding
                embedding = generate_recipe_embedding(recipe.name, recipe.description, recipe.tags)
                if embedding is not None:
                    recipe.embedding = embedding
                    self.database.db.commit()

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

        # Update steps if provided (delete-and-recreate)
        if params.steps is not None:
            existing_steps = self.database.where(
                RecipeStep,
                recipe_id=recipe_id
            ).all()
            for step in existing_steps:
                self.database.delete(step)

            for idx, step_input in enumerate(params.steps):
                new_step = RecipeStep(
                    recipe_id=recipe_id,
                    step_number=step_input.step_number if step_input.step_number is not None else idx + 1,
                    instruction=step_input.instruction,
                    active_time_minutes=step_input.active_time_minutes,
                    timers=step_input.timers,
                    wait_time_minutes=step_input.wait_time_minutes,
                    wait_type=step_input.wait_type,
                    can_prep_ahead=step_input.can_prep_ahead,
                    is_optional=step_input.is_optional,
                )
                self.database.create(new_step)

        # Fetch updated steps
        steps = self.database.where(
            RecipeStep,
            asc="step_number",
            recipe_id=recipe_id
        ).all()

        step_responses = [
            UpdateRecipe.StepResponse(
                id=str(step.id),
                step_number=step.step_number,
                instruction=step.instruction,
                active_time_minutes=step.active_time_minutes,
                timers=step.timers,
                wait_time_minutes=step.wait_time_minutes,
                wait_type=step.wait_type,
                can_prep_ahead=step.can_prep_ahead,
                is_optional=step.is_optional,
            )
            for step in steps
        ]

        # Fetch updated ingredients
        recipe_ingredients = (
            self.database.db.query(RecipeIngredient, Ingredient)
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

        # Get version count
        version_count = self.database.where(
            RecipeVersion,
            recipe_id=recipe_id,
        ).count()

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
                tags=recipe.tags or [],
                ingredients=ingredient_responses,
                steps=step_responses,
                created_at=recipe.created_at,
                updated_at=recipe.updated_at,
                version_count=version_count,
            )
        )

    def _create_version_snapshot(self, recipe, recipe_id, changed_fields, user):
        """Snapshot the current recipe state before applying updates."""
        # Fetch current ingredients
        current_ingredients = self.database.where(
            RecipeIngredient,
            recipe_id=recipe_id
        ).all()

        # Fetch current steps
        current_steps = self.database.where(
            RecipeStep,
            asc="step_number",
            recipe_id=recipe_id
        ).all()

        # Fetch current notes
        current_notes = self.database.where(
            RecipeNote,
            recipe_id=recipe_id,
            asc="created_at",
        ).all()

        snapshot = {
            "name": recipe.name,
            "description": recipe.description,
            "instructions": recipe.instructions,
            "servings": recipe.servings,
            "prep_time": recipe.prep_time,
            "cook_time": recipe.cook_time,
            "image_url": recipe.image_url,
            "source_url": recipe.source_url,
            "tags": recipe.tags or [],
            "ingredients": [
                {
                    "ingredient_id": str(ri.ingredient_id),
                    "quantity_display": format_quantity(ri.quantity_display, ri.unit_display),
                    "unit_display": ri.unit_display,
                    "notes": ri.notes,
                    "is_optional": ri.is_optional,
                    "order_index": ri.order_index,
                }
                for ri in current_ingredients
            ],
            "steps": [
                {
                    "step_number": step.step_number,
                    "instruction": step.instruction,
                    "active_time_minutes": step.active_time_minutes,
                    "timers": step.timers,
                    "wait_time_minutes": step.wait_time_minutes,
                    "wait_type": step.wait_type,
                    "can_prep_ahead": step.can_prep_ahead,
                    "is_optional": step.is_optional,
                }
                for step in current_steps
            ],
            "notes": [
                {
                    "body": n.body,
                    "created_by": str(n.created_by) if n.created_by else None,
                    "created_at": n.created_at.isoformat(),
                }
                for n in current_notes
            ],
        }

        # Get next version number
        max_version = (
            self.database.db.query(func.max(RecipeVersion.version_number))
            .filter(RecipeVersion.recipe_id == recipe_id)
            .scalar()
        ) or 0

        version = RecipeVersion(
            recipe_id=recipe_id,
            version_number=max_version + 1,
            snapshot=snapshot,
            changed_fields=changed_fields,
            created_by=user.id,
        )
        self.database.db.add(version)

    class IngredientInput(BaseModel):
        ingredient_id: str
        quantity: Decimal
        unit: str
        notes: str | None = None
        is_optional: bool = False

    class StepInput(BaseModel):
        step_number: int | None = None
        instruction: str
        active_time_minutes: int | None = None
        timers: list[dict] | None = None
        wait_time_minutes: int | None = None
        wait_type: str | None = None
        can_prep_ahead: bool = False
        is_optional: bool = False

    class Params(BaseModel):
        name: str | None = None
        description: str | None = None
        instructions: str | None = None
        servings: int | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        image_url: str | None = None
        source_url: str | None = None
        tags: list[str] | None = None
        ingredients: list["UpdateRecipe.IngredientInput"] | None = None
        steps: list["UpdateRecipe.StepInput"] | None = None

    class IngredientSummary(BaseModel):
        id: str
        canonical_name: str
        category: str | None = None

    class IngredientResponse(BaseModel):
        id: str
        ingredient: "UpdateRecipe.IngredientSummary"
        quantity_display: Decimal
        unit_display: str
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
        ingredients: list["UpdateRecipe.IngredientResponse"] = []
        steps: list["UpdateRecipe.StepResponse"] = []
        created_at: datetime
        updated_at: datetime
        version_count: int = 0
