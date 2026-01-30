"""Match ingredients task - matches extracted ingredients to existing ingredients."""

import logging

from sqlalchemy import func, text

from utils.api.endpoint import success
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.ingredient import Ingredient
from utils.models.ingredient_match import IngredientMatch
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.5


class MatchIngredientsTask(BaseTask):
    """Match extracted ingredients to existing ingredients.

    Uses tiered matching approach:
    1. Previous user-confirmed match (free)
    2. Exact canonical_name/alias match (free)
    3. pg_trgm fuzzy match > 0.85 (free, high confidence)
    4. pg_trgm fuzzy match > 0.5 (free, needs review)
    5. Auto-create with pending_review if no match
    """

    name = "match_ingredients_task"

    def execute(self, item_id: str):
        """Match ingredients for the given import item.

        Args:
            item_id: The ImportItem ID to process.

        Returns:
            Success response with matching results.
        """
        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            return success({"error": "Item not found", "item_id": item_id})

        if not item.parsed_recipe:
            item.status = "failed"
            item.error_message = "No parsed recipe data"
            item.error_code = "NO_PARSED_RECIPE"
            self.database.db.commit()
            return success({"error": "No parsed recipe", "item_id": item_id})

        try:
            ingredients = item.parsed_recipe.get("ingredients", [])
            matched_ingredients = []
            needs_review = False

            for _idx, ing_data in enumerate(ingredients):
                ing_text = ing_data.get("text", "")
                if not ing_text:
                    continue

                match_result = self._match_ingredient(ing_text)
                ing_data["matched_ingredient_id"] = match_result.get("ingredient_id")
                ing_data["match_confidence"] = match_result.get("confidence", 0)
                ing_data["match_type"] = match_result.get("match_type")
                ing_data["needs_review"] = match_result.get("needs_review", False)

                if match_result.get("needs_review"):
                    needs_review = True

                matched_ingredients.append(ing_data)

            # Update parsed_recipe with matched ingredients
            item.parsed_recipe["ingredients"] = matched_ingredients

            # Determine status
            if needs_review:
                item.status = "awaiting_review"
            else:
                # Auto-approve if all matches are high confidence
                item.status = "approved"

            self.database.db.commit()

            # Update job counts
            self._update_job_counts(item.import_job_id)

            # If approved, dispatch create recipe task
            if item.status == "approved":
                self._dispatch_create_task(item)

            return success({
                "item_id": item_id,
                "status": item.status,
                "ingredients_matched": len(matched_ingredients),
                "needs_review": needs_review,
            })

        except Exception as e:
            logger.exception("Error matching ingredients for item %s", item_id)
            item.status = "failed"
            item.error_message = str(e)
            item.error_code = "MATCHING_ERROR"
            self.database.db.commit()
            return success({"error": str(e), "item_id": item_id})

    def _match_ingredient(self, ingredient_text: str) -> dict:
        """Match a single ingredient text to an existing ingredient.

        Returns a dict with:
        - ingredient_id: UUID or None
        - confidence: float 0-1
        - match_type: str (exact, fuzzy, cached, created)
        - needs_review: bool
        """
        normalized = ingredient_text.lower().strip()

        # Tier 1: Check cached user-confirmed matches
        cached = self._check_cached_match(normalized)
        if cached:
            return cached

        # Tier 2: Exact match on canonical_name
        exact = self._exact_match(normalized)
        if exact:
            self._cache_match(ingredient_text, exact["ingredient_id"], "exact", 1.0)
            return exact

        # Tier 3: Fuzzy match using pg_trgm
        fuzzy = self._fuzzy_match(normalized)
        if fuzzy:
            self._cache_match(ingredient_text, fuzzy["ingredient_id"], "fuzzy", fuzzy["confidence"])
            return fuzzy

        # Tier 4: No match found - flag for review
        # In production, we might auto-create the ingredient with pending_review=True
        return {
            "ingredient_id": None,
            "confidence": 0,
            "match_type": "none",
            "needs_review": True,
        }

    def _check_cached_match(self, normalized_text: str) -> dict | None:
        """Check for a cached ingredient match."""
        match = self.database.db.query(IngredientMatch).filter(
            IngredientMatch.source_text_normalized == normalized_text,
            IngredientMatch.user_confirmed == True,  # noqa: E712
        ).first()

        if match and match.matched_ingredient_id:
            return {
                "ingredient_id": str(match.matched_ingredient_id),
                "confidence": match.confidence,
                "match_type": "cached",
                "needs_review": False,
            }

        return None

    def _exact_match(self, normalized_text: str) -> dict | None:
        """Exact match on canonical_name (case-insensitive)."""
        # Try to extract the ingredient name from the text
        # This is a simplified version - in production, we'd parse quantity/unit first
        ingredient_name = self._extract_ingredient_name(normalized_text)

        ingredient = self.database.db.query(Ingredient).filter(
            func.lower(Ingredient.canonical_name) == ingredient_name.lower()
        ).first()

        if ingredient:
            return {
                "ingredient_id": str(ingredient.id),
                "confidence": 1.0,
                "match_type": "exact",
                "needs_review": False,
            }

        return None

    def _fuzzy_match(self, normalized_text: str) -> dict | None:
        """Fuzzy match using pg_trgm similarity."""
        ingredient_name = self._extract_ingredient_name(normalized_text)

        # Use pg_trgm similarity function
        # This requires the pg_trgm extension to be installed
        try:
            result = self.database.db.execute(
                text("""
                    SELECT id, canonical_name, similarity(lower(canonical_name), :name) as sim
                    FROM ingredients
                    WHERE similarity(lower(canonical_name), :name) > :threshold
                    ORDER BY sim DESC
                    LIMIT 1
                """),
                {"name": ingredient_name.lower(), "threshold": MEDIUM_CONFIDENCE_THRESHOLD}
            ).first()

            if result:
                confidence = float(result.sim)
                return {
                    "ingredient_id": str(result.id),
                    "confidence": confidence,
                    "match_type": "fuzzy",
                    "needs_review": confidence < HIGH_CONFIDENCE_THRESHOLD,
                }
        except Exception as e:
            # pg_trgm might not be installed
            logger.warning("Fuzzy match failed (pg_trgm may not be installed): %s", e)

        return None

    def _extract_ingredient_name(self, text: str) -> str:
        """Extract ingredient name from full ingredient text.

        This is a simplified extraction that removes common quantity/unit patterns.
        A more robust version would use NLP or a dedicated parsing library.
        """
        import re

        # Remove common quantity patterns
        text = re.sub(r"^\d+[\./]?\d*\s*", "", text)  # "2", "1/2", "2.5"
        text = re.sub(r"^(cup|cups|tablespoon|tablespoons|tbsp|teaspoon|teaspoons|tsp|"
                      r"ounce|ounces|oz|pound|pounds|lb|lbs|gram|grams|g|kg|ml|l|"
                      r"clove|cloves|piece|pieces|can|cans|package|packages|bunch|bunches|"
                      r"large|medium|small|whole|half|quarter|pinch|dash|to taste)\s+",
                      "", text, flags=re.IGNORECASE)

        # Remove text in parentheses (often notes)
        text = re.sub(r"\([^)]*\)", "", text)

        # Remove common suffixes
        text = re.sub(r",.*$", "", text)  # Remove everything after comma

        return text.strip()

    def _cache_match(self, source_text: str, ingredient_id: str, match_type: str, confidence: float):
        """Cache a match for future lookups."""
        existing = self.database.db.query(IngredientMatch).filter(
            IngredientMatch.source_text_normalized == source_text.lower().strip()
        ).first()

        if existing:
            # Update existing
            existing.matched_ingredient_id = ingredient_id
            existing.match_type = match_type
            existing.confidence = confidence
        else:
            # Create new
            match = IngredientMatch(
                source_text=source_text,
                source_text_normalized=source_text.lower().strip(),
                matched_ingredient_id=ingredient_id,
                match_type=match_type,
                confidence=confidence,
                user_id=self.user_id,
            )
            self.database.create(match)

    def _update_job_counts(self, import_job_id):
        """Update import job counts."""
        job = self.database.find_by(ImportJob, id=import_job_id)
        if not job:
            return

        from sqlalchemy import func as sqlfunc

        counts = self.database.db.query(
            ImportItem.status,
            sqlfunc.count(ImportItem.id)
        ).filter(
            ImportItem.import_job_id == import_job_id
        ).group_by(ImportItem.status).all()

        status_counts = dict(counts)

        job.pending_review_items = status_counts.get("awaiting_review", 0)
        job.succeeded_items = status_counts.get("completed", 0)

        # Update job status
        total_done = sum(
            status_counts.get(s, 0)
            for s in ["completed", "failed", "skipped", "awaiting_review", "approved"]
        )

        if total_done >= job.total_items:
            if job.pending_review_items > 0:
                job.status = "awaiting_review"
            elif status_counts.get("approved", 0) > 0:
                job.status = "processing"  # Still creating recipes
            else:
                job.status = "completed"

        self.database.db.commit()

    def _dispatch_create_task(self, item: ImportItem):
        """Dispatch create recipe task for approved item."""
        from utils.tasks.import_tasks.create_recipe_task import create_recipe_task

        create_recipe_task.delay(
            item_id=str(item.id),
            user_id=str(self.user_id) if self.user_id else None,
        )


# Register task with Celery
match_ingredients_task = celery_app.register_task(MatchIngredientsTask())
