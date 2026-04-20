"""Extract recipe task - extracts recipe data from import items."""

import asyncio
import json
import logging

from utils.api.endpoint import success
from utils.constants import STAGE_EXTRACTED
from utils.logging import log_stage_transition
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.services.celery import celery_app
from utils.services.recipe_extractors import (
    ExtractionResult,
    extract_recipe_from_text,
    extract_recipe_from_url,
)
from utils.services.recipe_extractors.video_extractor import extract_recipe_from_video
from utils.services.units import normalize_unit_display
from utils.services.url_classifier import is_social_media_url
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)


def _serialize_recipe(recipe, extractor_used: str | None, session) -> dict:
    """Serialize an ExtractedRecipe into the `parsed_recipe` JSONB shape.

    Structured `steps`, when available, are the preferred format
    downstream. `create_recipe_task` already reads this field and
    creates one recipe_step row per entry. When the extractor couldn't
    produce structured steps (or the LLM returned malformed data) we
    fall through to the legacy `instructions` string, which
    `create_recipe_task` splits with a regex.

    `unit` on each ingredient is run through `normalize_unit_display`
    (riip-2) so freeform LLM output ("tablespoon") gets coerced to the
    canonical token ("tbsp") before the parsed_recipe JSON ever lands.
    """
    steps_dict = (
        [
            {
                "order": s.order,
                "instruction": s.instruction,
                # cmt-1 — pass through the raw `timers` list. Clamp +
                # filter happens at persist time in create_recipe_task.
                "timers": list(getattr(s, "timers", []) or []),
            }
            for s in recipe.steps
        ]
        if recipe.steps
        else None
    )
    return {
        "name": recipe.name,
        "description": recipe.description,
        "ingredients": [
            {
                "text": ing.text,
                "quantity": ing.quantity,
                "unit": normalize_unit_display(
                    ing.unit, session, context={"path": "extract_recipe_task"}
                ),
                "name": ing.name,
                "notes": ing.notes,
                "is_optional": ing.is_optional,
            }
            for ing in recipe.ingredients
        ],
        "steps": steps_dict,
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
        "primary_vibe": recipe.primary_vibe,
        "secondary_vibe": recipe.secondary_vibe,
        # irrd-3 — persisted at the top level of parsed_recipe for easy
        # hoisting onto GetImportItem / ListImportItems responses.
        # `getattr` guards against mock callers that don't set these.
        "confidence_score": getattr(recipe, "confidence_score", None),
        "confidence_source": getattr(recipe, "confidence_source", None),
        "extractor_used": extractor_used,
    }


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

        # Stage-transition audit (irrd-2): entering the extract stage.
        log_stage_transition(
            import_item_id=item.id,
            stage=STAGE_EXTRACTED,
            status="started",
        )

        try:
            if item.source_type == "photo":
                # Extract from OCR text using AI
                ocr_text = (item.raw_data or {}).get("text", "")
                result = extract_recipe_from_text(ocr_text)
                self._update_item_from_result(item, result)
            elif item.source_url and is_social_media_url(item.source_url):
                # Extract from social media video metadata
                result = extract_recipe_from_video(item.source_url)
                self._update_item_from_result(item, result)
            elif item.source_url:
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

            # Stage-transition audit (irrd-2): extraction produced a
            # parsed_recipe. Preview is the pretty-printed JSON (truncation
            # happens inside the helper).
            preview = None
            if item.parsed_recipe:
                try:
                    preview = json.dumps(
                        item.parsed_recipe, indent=2, default=str, sort_keys=True
                    )
                except Exception:
                    preview = None
            log_stage_transition(
                import_item_id=item.id,
                stage=STAGE_EXTRACTED,
                status="ok",
                raw_output_preview=preview,
            )

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

            # Stage-transition audit (irrd-2): extract stage failed.
            log_stage_transition(
                import_item_id=item.id,
                stage=STAGE_EXTRACTED,
                status="failed",
                error_message=str(e),
            )

            self._update_job_counts(item.import_job_id)

            # Create failure activity
            try:
                from utils.services.activity_service import create_activity

                job = self.database.find_by(ImportJob, id=item.import_job_id)
                if job:
                    create_activity(
                        self.database.db,
                        user_id=job.user_id,
                        activity_type="import_failed",
                        title="Import failed",
                        subtitle=str(e),
                        metadata={
                            "import_job_id": str(item.import_job_id),
                            "import_item_id": str(item_id),
                            "error": str(e),
                        },
                        action_url=f"/recipes/import/review-list/{item.import_job_id}",
                    )
                    self.database.db.commit()
            except Exception:
                logger.warning("Failed to create extraction-failure activity", exc_info=True)

            return {
                "item_id": item_id,
                "status": "failed",
                "error": str(e),
            }

    def _update_item_from_result(self, item: ImportItem, result: ExtractionResult):
        """Update import item from extraction result.

        When the extractor returns multiple recipes (`len(recipes) > 1`),
        fans out siblings on the same ImportJob, one ImportItem per
        recipe. The first recipe lands in the original item; the rest
        are new rows with copies of `raw_data` (same s3_keys) plus a
        `recipe_index` ordinal for dedupe/traceability. `total_items` is
        bumped atomically. Post-extraction, items rest in `awaiting_review`
        until the user approves (or the item is dismissed); approval
        dispatches `create_recipe_task`.
        """
        item.ai_cost_cents = result.ai_cost_cents

        if not (result.success and result.recipes):
            item.status = "failed"
            item.error_message = result.error_message
            item.error_code = result.error_code
            item.retry_count += 1
            self.database.db.commit()
            self._update_job_counts(item.import_job_id)
            return

        recipes = result.recipes
        extractor_used = result.extractor_used

        # Write the first recipe into the existing item.
        item.parsed_recipe = _serialize_recipe(recipes[0], extractor_used, self.database.db)
        item.raw_data = {**(item.raw_data or {}), "recipe_index": 0}
        item.status = "awaiting_review"
        item.last_successful_stage = STAGE_EXTRACTED

        # Fan out siblings for recipes[1..N-1].
        siblings: list[ImportItem] = []
        if len(recipes) > 1:
            siblings = self._create_fanout_siblings(item, recipes, extractor_used)

        self.database.db.commit()

        # Job AI cost only reflects the original extractor call; siblings
        # contribute 0 so we don't double-count.
        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if job:
            if result.ai_cost_cents > 0:
                job.total_ai_cost_cents += result.ai_cost_cents
            if siblings:
                job.total_items = (job.total_items or 0) + len(siblings)
            self.database.db.commit()

        self._update_job_counts(item.import_job_id)

    def _create_fanout_siblings(
        self,
        original: ImportItem,
        recipes: list,
        extractor_used: str | None,
    ) -> list[ImportItem]:
        """Create sibling ImportItems for recipes[1..N-1].

        Idempotent: if a sibling for `(import_job_id, s3_keys, recipe_index)`
        already exists (e.g. this task was retried by Celery), skip it.
        Returns the list of newly-created siblings for downstream bookkeeping.
        """
        from sqlalchemy import select

        base_raw = dict(original.raw_data or {})
        source_keys = base_raw.get("s3_keys") or []

        # One query to find which recipe_index values are already materialized
        # on this job. The dedupe key is (job_id, s3_keys, recipe_index) per
        # the epic; in practice s3_keys is a stable list for a single photo
        # import, so comparing s3_keys at the Python layer is sufficient.
        existing = self.database.db.scalars(
            select(ImportItem).where(ImportItem.import_job_id == original.import_job_id)
        ).all()
        existing_indices: set[int] = set()
        for row in existing:
            rd = row.raw_data or {}
            if rd.get("s3_keys") == source_keys and "recipe_index" in rd:
                try:
                    existing_indices.add(int(rd["recipe_index"]))
                except (TypeError, ValueError):
                    continue

        created: list[ImportItem] = []
        for idx in range(1, len(recipes)):
            if idx in existing_indices:
                logger.info(
                    "Skipping fanout for item %s recipe_index=%d (already exists)",
                    original.id,
                    idx,
                )
                continue
            sibling = ImportItem(
                import_job_id=original.import_job_id,
                source_type=original.source_type,
                source_reference=original.source_reference,
                source_url=original.source_url,
                status="awaiting_review",
                last_successful_stage=STAGE_EXTRACTED,
                parsed_recipe=_serialize_recipe(
                    recipes[idx], extractor_used, self.database.db
                ),
                raw_data={**base_raw, "recipe_index": idx},
                ai_cost_cents=0,
            )
            self.database.create(sibling)
            created.append(sibling)
        return created

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
        item.status = "awaiting_review"
        item.last_successful_stage = STAGE_EXTRACTED
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
                        # Coerce freeform unit input to canonical (riip-2).
                        "unit": normalize_unit_display(
                            ing.get("unit"),
                            self.database.db,
                            context={"path": "extract_recipe_task.raw_data"},
                        ),
                        "name": ing.get("name"),
                    })
            return result

        return []

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

        previous_status = job.status

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

        if (
            job.status == "awaiting_review"
            and previous_status != "awaiting_review"
        ):
            from utils.services.import_notifications import (
                notify_import_needs_review,
            )

            notify_import_needs_review(self.database, job)


# Register task with Celery
extract_task = celery_app.register_task(ExtractRecipeTask())
