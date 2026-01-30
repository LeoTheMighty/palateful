"""Create recipe task - creates Recipe records from approved import items."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from utils.api.endpoint import success
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe import Recipe
from utils.models.recipe_ingredient import RecipeIngredient
from utils.services.celery import celery_app
from utils.services.units.conversion import normalize_quantity
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)


class CreateRecipeTask(BaseTask):
    """Create Recipe records from approved import items.

    This task finalizes the import by creating the actual Recipe
    and RecipeIngredient records in the database.
    """

    name = "create_recipe_task"

    def execute(self, item_id: str):
        """Create a Recipe from the approved import item.

        Args:
            item_id: The ImportItem ID to process.

        Returns:
            Success response with created recipe ID.
        """
        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            return success({"error": "Item not found", "item_id": item_id})

        # Verify item is approved
        if item.status not in ("approved", "awaiting_review"):
            return success({
                "error": f"Item is not approved (status: {item.status})",
                "item_id": item_id,
            })

        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if not job:
            return success({"error": "Import job not found", "item_id": item_id})

        try:
            # Get recipe data (use user_edits if present, otherwise parsed_recipe)
            recipe_data = item.user_edits or item.parsed_recipe
            if not recipe_data:
                item.status = "failed"
                item.error_message = "No recipe data available"
                self.database.db.commit()
                return success({"error": "No recipe data", "item_id": item_id})

            # Create the Recipe
            recipe = Recipe(
                name=recipe_data.get("name", "Imported Recipe"),
                description=recipe_data.get("description"),
                instructions=recipe_data.get("instructions"),
                servings=recipe_data.get("servings") or 1,
                prep_time=recipe_data.get("prep_time_minutes"),
                cook_time=recipe_data.get("cook_time_minutes"),
                image_url=recipe_data.get("image_url"),
                source_url=recipe_data.get("source_url") or item.source_url,
                recipe_book_id=job.recipe_book_id,
            )
            self.database.create(recipe)
            self.database.db.refresh(recipe)

            # Create RecipeIngredient records
            ingredients_data = recipe_data.get("ingredients", [])
            for idx, ing_data in enumerate(ingredients_data):
                self._create_recipe_ingredient(recipe, ing_data, idx)

            # Update import item
            item.status = "completed"
            item.created_recipe_id = recipe.id
            self.database.db.commit()

            # Update job counts
            self._update_job_counts(job)

            return success({
                "item_id": item_id,
                "recipe_id": str(recipe.id),
                "status": "completed",
            })

        except Exception as e:
            logger.exception("Error creating recipe for item %s", item_id)
            item.status = "failed"
            item.error_message = str(e)
            item.error_code = "CREATE_RECIPE_ERROR"
            self.database.db.commit()
            return success({"error": str(e), "item_id": item_id})

    def _create_recipe_ingredient(self, recipe: Recipe, ing_data: dict, order_index: int):
        """Create a RecipeIngredient record."""
        ingredient_id = ing_data.get("matched_ingredient_id")
        if not ingredient_id:
            # Skip ingredients without a match
            # In production, we might create a placeholder ingredient
            logger.warning("Skipping ingredient without match: %s", ing_data.get("text"))
            return

        # Parse quantity
        quantity = ing_data.get("quantity")
        if quantity is not None:
            try:
                quantity = Decimal(str(quantity))
            except (ValueError, TypeError):
                quantity = Decimal("1")
        else:
            quantity = Decimal("1")

        unit = ing_data.get("unit", "")

        # Normalize quantity if possible
        try:
            normalized = normalize_quantity(float(quantity), unit)
            quantity_normalized = Decimal(str(normalized.quantity_normalized))
            unit_normalized = normalized.unit_normalized
        except Exception:
            quantity_normalized = quantity
            unit_normalized = unit

        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ingredient_id,
            quantity_display=quantity,
            unit_display=unit,
            quantity_normalized=quantity_normalized,
            unit_normalized=unit_normalized,
            notes=ing_data.get("notes"),
            is_optional=ing_data.get("is_optional", False),
            order_index=order_index,
        )
        self.database.create(recipe_ingredient)

    def _update_job_counts(self, job: ImportJob):
        """Update import job counts and status."""
        from sqlalchemy import func

        counts = self.database.db.query(
            ImportItem.status,
            func.count(ImportItem.id)
        ).filter(
            ImportItem.import_job_id == job.id
        ).group_by(ImportItem.status).all()

        status_counts = dict(counts)

        job.succeeded_items = status_counts.get("completed", 0)
        job.failed_items = status_counts.get("failed", 0)
        job.pending_review_items = status_counts.get("awaiting_review", 0)

        # Calculate processed
        job.processed_items = sum(
            status_counts.get(s, 0)
            for s in ["completed", "failed", "skipped"]
        )

        # Check if job is complete
        total_final = job.succeeded_items + job.failed_items + status_counts.get("skipped", 0)
        if total_final >= job.total_items:
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
        elif job.pending_review_items > 0:
            job.status = "awaiting_review"

        self.database.db.commit()


# Register task with Celery
create_recipe_task = celery_app.register_task(CreateRecipeTask())
