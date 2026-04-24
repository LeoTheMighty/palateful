"""Restore a recipe to a previous version."""

from datetime import datetime
from decimal import Decimal
from fractions import Fraction

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import APIException, AsyncEndpoint, success
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
from utils.services.units import normalize_unit_display
from utils.services.units.conversion import normalize_quantity


def _parse_quantity_display(s: str) -> Decimal:
    """Parse a formatted quantity string back to Decimal.

    Handles '2', '0.5', '1/2', '1 1/4', etc.
    Used to convert snapshot quantity_display values (formatted strings)
    back to Decimal for storage in RecipeIngredient.
    """
    try:
        s = s.strip()
        parts = s.split(' ')
        if len(parts) == 2:
            # "1 1/2" → whole + fraction
            whole = int(parts[0])
            frac = Fraction(parts[1])
            return Decimal(str(float(whole + frac)))
        else:
            # "1/2", "2", "0.5"
            return Decimal(str(float(Fraction(s))))
    except Exception:
        return Decimal(s)


class RestoreRecipeVersion(AsyncEndpoint):
    """Restore a recipe to a previous version snapshot.

    Creates a new version capturing the current state (never destroys history),
    then applies the selected snapshot to the recipe.
    """

    async def execute(self, recipe_id: str, version_id: str):
        user: User = self.user

        # Load recipe
        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail=f"Recipe with ID '{recipe_id}' not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Owner or editor required
        membership = await self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to restore this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        # Load the version to restore
        version = await self.database.find_by(RecipeVersion, id=version_id)
        if not version or str(version.recipe_id) != str(recipe_id):
            raise APIException(
                status_code=404,
                detail=f"Version with ID '{version_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )

        snapshot = version.snapshot

        # Snapshot current state BEFORE overwriting (append-only — never destroy history)
        await self._create_restore_snapshot(recipe, recipe_id, version.version_number, user)

        # Apply snapshot: update recipe scalar fields
        updates = {}
        if "name" in snapshot:
            updates["name"] = snapshot["name"]
        if "instructions" in snapshot:
            updates["instructions"] = snapshot["instructions"]
        if updates:
            await self.database.update(recipe, **updates)

        # Recreate ingredients from snapshot
        existing_ingredients = await self.database.where(
            RecipeIngredient, recipe_id=recipe_id
        ).all()
        for ri in existing_ingredients:
            await self.database.delete(ri)

        for ing_data in snapshot.get("ingredients", []):
            qty_str = ing_data.get("quantity_display", "1")
            # Snapshots preserve history (un-normalized), but restoring a
            # row to live state runs the unit through the canonical
            # normalizer (riip-2 design principle 5). `normalize_unit_display`
            # stays sync; pre-warmed module cache avoids session I/O.
            unit = normalize_unit_display(
                ing_data.get("unit_display", ""),
                self.database.db,
                context={"path": "restore_recipe_version"},
            ) or ""
            try:
                qty_decimal = _parse_quantity_display(str(qty_str))
            except Exception:
                qty_decimal = Decimal("1")

            try:
                normalized = normalize_quantity(float(qty_decimal), unit)
                qty_normalized = Decimal(str(normalized.quantity_normalized))
                unit_normalized = normalized.unit_normalized
            except Exception:
                qty_normalized = qty_decimal
                unit_normalized = unit

            new_ri = RecipeIngredient(
                recipe_id=recipe_id,
                ingredient_id=ing_data["ingredient_id"],
                quantity_display=qty_decimal,
                unit_display=unit,
                quantity_normalized=qty_normalized,
                unit_normalized=unit_normalized,
                notes=ing_data.get("notes"),
                is_optional=ing_data.get("is_optional", False),
                order_index=ing_data.get("order_index", 0),
            )
            await self.database.create(new_ri)

        # Recreate steps from snapshot
        existing_steps = await self.database.where(
            RecipeStep, recipe_id=recipe_id
        ).all()
        for step in existing_steps:
            await self.database.delete(step)

        for step_data in snapshot.get("steps", []):
            new_step = RecipeStep(
                recipe_id=recipe_id,
                step_number=step_data["step_number"],
                instruction=step_data.get("instruction", ""),
                active_time_minutes=step_data.get("active_time_minutes"),
                timers=step_data.get("timers"),
                wait_time_minutes=step_data.get("wait_time_minutes"),
                wait_type=step_data.get("wait_type"),
                can_prep_ahead=step_data.get("can_prep_ahead", False),
                is_optional=step_data.get("is_optional", False),
            )
            await self.database.create(new_step)

        # Fetch updated data for response
        updated_steps = await self.database.where(
            RecipeStep,
            asc="step_number",
            recipe_id=recipe_id,
        ).all()

        step_responses = [
            RestoreRecipeVersion.StepResponse(
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
            for s in updated_steps
        ]

        ri_result = await self.database.db.execute(
            select(RecipeIngredient, Ingredient)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .where(RecipeIngredient.recipe_id == recipe_id)
            .order_by(RecipeIngredient.order_index)
        )
        updated_ingredients = list(ri_result.all())

        ingredient_responses = [
            RestoreRecipeVersion.IngredientResponse(
                id=str(ri.ingredient_id),
                ingredient=RestoreRecipeVersion.IngredientSummary(
                    id=str(ing.id),
                    canonical_name=ing.canonical_name,
                ),
                quantity_display=format_quantity(ri.quantity_display, ri.unit_display),
                unit_display=ri.unit_display,
                notes=ri.notes,
                is_optional=ri.is_optional,
                order_index=ri.order_index,
            )
            for ri, ing in updated_ingredients
        ]

        version_count = await self.database.where(
            RecipeVersion,
            recipe_id=recipe_id,
        ).count()

        return success(
            data=RestoreRecipeVersion.Response(
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
                created_at=recipe.created_at,
                updated_at=recipe.updated_at,
                version_count=version_count,
            )
        )

    async def _create_restore_snapshot(self, recipe, recipe_id, restored_from_version_number, user):
        """Snapshot the current state with changed_fields indicating a restore operation."""
        current_ingredients = await self.database.where(
            RecipeIngredient, recipe_id=recipe_id
        ).all()
        current_steps = await self.database.where(
            RecipeStep, asc="step_number", recipe_id=recipe_id
        ).all()
        current_notes = await self.database.where(
            RecipeNote, recipe_id=recipe_id, asc="created_at"
        ).all()

        snapshot = {
            "name": recipe.name,
            "instructions": recipe.instructions,
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
                    "step_number": s.step_number,
                    "instruction": s.instruction,
                    "active_time_minutes": s.active_time_minutes,
                    "timers": s.timers,
                    "wait_time_minutes": s.wait_time_minutes,
                    "wait_type": s.wait_type,
                    "can_prep_ahead": s.can_prep_ahead,
                    "is_optional": s.is_optional,
                }
                for s in current_steps
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

        max_version_result = await self.database.db.execute(
            select(func.max(RecipeVersion.version_number))
            .where(RecipeVersion.recipe_id == recipe_id)
        )
        max_version = max_version_result.scalar() or 0

        version = RecipeVersion(
            recipe_id=recipe_id,
            version_number=max_version + 1,
            snapshot=snapshot,
            changed_fields=[f"restore:{restored_from_version_number}"],
            created_by=user.id,
        )
        self.database.db.add(version)

    class IngredientSummary(BaseModel):
        id: str
        canonical_name: str
        category: str | None = None

    class IngredientResponse(BaseModel):
        id: str
        ingredient: "RestoreRecipeVersion.IngredientSummary"
        quantity_display: str
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
        ingredients: list["RestoreRecipeVersion.IngredientResponse"] = []
        steps: list["RestoreRecipeVersion.StepResponse"] = []
        created_at: datetime
        updated_at: datetime
        version_count: int = 0
