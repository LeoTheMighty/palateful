"""Extract recipe task - extracts recipe data from import items."""

import asyncio
import logging

from utils.api.endpoint import success
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.services.celery import celery_app
from utils.services.recipe_extractors import ExtractionResult, extract_recipe_from_url
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)


class ExtractRecipeTask(BaseTask):
    """Extract recipe data from import items.

    Uses tiered extraction approach:
    1. JSON-LD (free)
    2. Microdata (free) - future
    3. Site-specific scrapers (free) - future
    4. AI extraction (paid, ~$0.002 per recipe)
    """

    name = "extract_recipe_task"

    def execute(self, item_ids: list[str]):
        """Extract recipe data from the given items.

        Args:
            item_ids: List of ImportItem IDs to process.

        Returns:
            Success response with extraction results.
        """
        results = []

        for item_id in item_ids:
            result = self._extract_single_item(item_id)
            results.append(result)

        return success({
            "processed": len(results),
            "results": results,
        })

    def _extract_single_item(self, item_id: str) -> dict:
        """Extract recipe from a single import item."""
        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            return {"item_id": item_id, "error": "Item not found"}

        # Update status
        item.status = "extracting"
        self.database.db.commit()

        try:
            if item.source_url:
                # Extract from URL
                result = asyncio.run(
                    extract_recipe_from_url(
                        item.source_url,
                        use_ai_fallback=True,
                    )
                )
                self._update_item_from_result(item, result)
            else:
                # Extract from raw_data (spreadsheet row)
                self._extract_from_raw_data(item)

            # Dispatch ingredient matching if extraction succeeded
            if item.status == "matching" or item.status == "awaiting_review":
                self._dispatch_matching_task(item)

            return {
                "item_id": item_id,
                "status": item.status,
                "ai_cost_cents": item.ai_cost_cents,
            }

        except Exception as e:
            logger.exception("Error extracting recipe for item %s", item_id)
            item.status = "failed"
            item.error_message = str(e)
            item.error_code = "EXTRACTION_ERROR"
            item.retry_count += 1
            self.database.db.commit()

            self._update_job_counts(item.import_job_id)

            return {
                "item_id": item_id,
                "status": "failed",
                "error": str(e),
            }

    def _update_item_from_result(self, item: ImportItem, result: ExtractionResult):
        """Update import item from extraction result."""
        item.ai_cost_cents = result.ai_cost_cents

        if result.success and result.recipe:
            # Store parsed recipe as dict
            recipe = result.recipe
            item.parsed_recipe = {
                "name": recipe.name,
                "description": recipe.description,
                "ingredients": [
                    {
                        "text": ing.text,
                        "quantity": ing.quantity,
                        "unit": ing.unit,
                        "name": ing.name,
                        "notes": ing.notes,
                        "is_optional": ing.is_optional,
                    }
                    for ing in recipe.ingredients
                ],
                "instructions": recipe.instructions,
                "servings": recipe.servings,
                "prep_time_minutes": recipe.prep_time_minutes,
                "cook_time_minutes": recipe.cook_time_minutes,
                "total_time_minutes": recipe.total_time_minutes,
                "image_url": recipe.image_url,
                "source_url": recipe.source_url,
                "author": recipe.author,
                "cuisine": recipe.cuisine,
                "category": recipe.category,
                "keywords": recipe.keywords,
                "extractor_used": result.extractor_used,
            }
            # Move to matching stage
            item.status = "matching"
        else:
            item.status = "failed"
            item.error_message = result.error_message
            item.error_code = result.error_code
            item.retry_count += 1

        self.database.db.commit()

        # Update job AI cost
        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if job and result.ai_cost_cents > 0:
            job.total_ai_cost_cents += result.ai_cost_cents
            self.database.db.commit()

        # Update job counts
        self._update_job_counts(item.import_job_id)

    def _extract_from_raw_data(self, item: ImportItem):
        """Extract recipe from raw spreadsheet/form data.

        This handles cases where the recipe data was provided directly
        rather than as a URL to scrape.
        """
        raw = item.raw_data
        if not raw:
            item.status = "failed"
            item.error_message = "No raw data to extract from"
            item.error_code = "NO_RAW_DATA"
            self.database.db.commit()
            return

        # Map raw data to parsed recipe format
        item.parsed_recipe = {
            "name": raw.get("name") or raw.get("title") or "Untitled Recipe",
            "description": raw.get("description"),
            "ingredients": self._parse_raw_ingredients(raw.get("ingredients", [])),
            "instructions": raw.get("instructions") or raw.get("directions"),
            "servings": raw.get("servings"),
            "prep_time_minutes": raw.get("prep_time") or raw.get("prep_time_minutes"),
            "cook_time_minutes": raw.get("cook_time") or raw.get("cook_time_minutes"),
            "image_url": raw.get("image_url") or raw.get("image"),
            "source_url": raw.get("source_url") or raw.get("url"),
        }
        item.status = "matching"
        self.database.db.commit()

    def _parse_raw_ingredients(self, ingredients) -> list[dict]:
        """Parse ingredients from raw data format."""
        if not ingredients:
            return []

        if isinstance(ingredients, str):
            # Split by newlines
            lines = [line.strip() for line in ingredients.split("\n") if line.strip()]
            return [{"text": line} for line in lines]

        if isinstance(ingredients, list):
            result = []
            for ing in ingredients:
                if isinstance(ing, str):
                    result.append({"text": ing})
                elif isinstance(ing, dict):
                    result.append({
                        "text": ing.get("text", ""),
                        "quantity": ing.get("quantity"),
                        "unit": ing.get("unit"),
                        "name": ing.get("name"),
                    })
            return result

        return []

    def _dispatch_matching_task(self, item: ImportItem):
        """Dispatch ingredient matching task for the item."""
        from utils.tasks.import_tasks.match_ingredients_task import match_ingredients_task

        match_ingredients_task.delay(
            item_id=str(item.id),
            user_id=str(self.user_id) if self.user_id else None,
        )

    def _update_job_counts(self, import_job_id):
        """Update import job processed/failed counts."""
        job = self.database.find_by(ImportJob, id=import_job_id)
        if not job:
            return

        # Count items in each status
        from sqlalchemy import func

        counts = self.database.db.query(
            ImportItem.status,
            func.count(ImportItem.id)
        ).filter(
            ImportItem.import_job_id == import_job_id
        ).group_by(ImportItem.status).all()

        status_counts = dict(counts)

        job.processed_items = sum(
            status_counts.get(s, 0)
            for s in ["matching", "awaiting_review", "approved", "completed", "failed", "skipped"]
        )
        job.failed_items = status_counts.get("failed", 0)
        job.succeeded_items = status_counts.get("completed", 0)
        job.pending_review_items = status_counts.get("awaiting_review", 0)

        # Check if job is complete
        total_processed = job.processed_items
        if total_processed >= job.total_items:
            if job.failed_items == job.total_items:
                job.status = "failed"
            elif job.pending_review_items > 0:
                job.status = "awaiting_review"
            else:
                job.status = "completed"

        self.database.db.commit()


# Register task with Celery
extract_task = celery_app.register_task(ExtractRecipeTask())
