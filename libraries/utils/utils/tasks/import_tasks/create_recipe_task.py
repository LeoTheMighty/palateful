"""Create recipe task - creates Recipe records from approved import items."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from utils.api.endpoint import success
from utils.constants import (
    AWS_REGION,
    BATCH_JOB_DEFINITION,
    BATCH_JOB_QUEUE,
    PARSER_INPUTS_BUCKET,
    PARSER_OUTPUTS_BUCKET,
    STAGE_CREATED,
)
from utils.logging import log_stage_transition
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_step import RecipeStep
from utils.services.aws import AWSService
from utils.services.celery import celery_app
from utils.services.recipe_extractors.inference_prompt import INFERABLE_FIELDS
from utils.services.recipe_image_promotion import promote_source_photo
from utils.services.units import normalize_unit_display
from utils.services.units.conversion import normalize_quantity
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# cmt-2 — timer clamp bounds. Mirrored in the Flutter manual-timer
# sheet and the step-timer regex helper so extractor, manual-entry, and
# regex-derived timers all obey the same contract.
_TIMER_MIN_MINUTES = 1
_TIMER_MAX_MINUTES = 360
_TIMER_MAX_PER_STEP = 10
_TIMER_LABEL_MAX_LEN = 40


def _clamp_timers(raw_timers) -> tuple[list[dict], int]:
    """Validate + clamp a list of timer dicts.

    Returns (clean_timers, dropped_count). Rules:
      * Non-list inputs -> ([], 0). (Schema allows absent/null.)
      * Cap at _TIMER_MAX_PER_STEP entries; overflow counted as dropped.
      * Each entry must be a dict with `duration_minutes` that is an
        `int` in [_TIMER_MIN_MINUTES, _TIMER_MAX_MINUTES] -- booleans
        don't count as ints.
      * `label` coerced to `str`, `.strip()`, truncated to
        _TIMER_LABEL_MAX_LEN. Empty/missing -> "timer".
      * Anything else increments `dropped`.
    """
    if not isinstance(raw_timers, list):
        return [], 0

    clean: list[dict] = []
    dropped = 0
    for entry in raw_timers[:_TIMER_MAX_PER_STEP]:
        if not isinstance(entry, dict):
            dropped += 1
            continue
        dur = entry.get("duration_minutes")
        # isinstance(True, int) is True in Python -- reject booleans
        # explicitly to avoid "True min" timers leaking through.
        if isinstance(dur, bool) or not isinstance(dur, int):
            dropped += 1
            continue
        if dur < _TIMER_MIN_MINUTES or dur > _TIMER_MAX_MINUTES:
            dropped += 1
            continue
        label_raw = entry.get("label", "")
        label = label_raw if isinstance(label_raw, str) else ""
        label = label.strip()[:_TIMER_LABEL_MAX_LEN]
        if not label:
            label = "timer"
        clean.append({"duration_minutes": dur, "label": label})

    if len(raw_timers) > _TIMER_MAX_PER_STEP:
        dropped += len(raw_timers) - _TIMER_MAX_PER_STEP

    return clean, dropped


def _log_timer_clamp(
    db,
    *,
    recipe_name: str,
    step_order,
    dropped_count: int,
    raw_input,
) -> None:
    """cmt-2 — independent audit row for every dropped timer.

    Uses its own try/except + `db.commit()` so the audit row survives
    even if the main import transaction rolls back. Pattern copied from
    `advance_recurrence_windows._log_audit`.
    """
    try:
        from utils.models.error_log import ErrorLog  # local import — avoid cycles

        sample = repr(raw_input)[:200] if raw_input is not None else ""
        message = (
            f"TimerClamp dropped={dropped_count} "
            f"recipe={recipe_name!r} step={step_order} sample={sample}"
        )
        entry = ErrorLog(
            service="worker",
            error_type="TimerClamp",
            error_message=message,
        )
        db.add(entry)
        db.commit()
    except Exception:
        logger.exception("Failed to write TimerClamp audit row")


def _filter_inferred_fields(raw) -> list[str]:
    """efi-3 — allow-list filter + dedupe for ``inferred_fields``.

    Defense in depth: the extractor's ``parse_inferred_fields`` already
    filters to ``INFERABLE_FIELDS``, but ``user_edits`` is a
    client-supplied payload that could re-introduce bogus names. We
    re-check here so a malformed edit can't smuggle a non-inferable
    field onto the Recipe row.

    Accepts anything (None, non-list, dicts, stringly-typed garbage)
    and always returns a clean ``list[str]`` preserving first-seen
    order.
    """
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    clean: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        if item in INFERABLE_FIELDS and item not in seen:
            seen.add(item)
            clean.append(item)
    return clean


_aws_service: AWSService | None = None


def _get_aws_service() -> AWSService:
    """Lazy-init an AWSService singleton for the worker process.

    Mirrors the API-side singleton pattern in
    `services/api/src/api/v1/recipe/get_photo_upload_url.py`. Pulled
    from `utils.constants` which read the worker's env vars directly,
    matching watch_parser_batch_task's AWS access.
    """
    global _aws_service
    if _aws_service is None:
        _aws_service = AWSService(
            region=AWS_REGION,
            parser_inputs_bucket=PARSER_INPUTS_BUCKET,
            parser_outputs_bucket=PARSER_OUTPUTS_BUCKET,
            batch_job_queue=BATCH_JOB_QUEUE,
            batch_job_definition=BATCH_JOB_DEFINITION,
        )
    return _aws_service


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

        # Stage-transition audit (irrd-2): entering the create stage.
        log_stage_transition(
            import_item_id=item.id,
            stage=STAGE_CREATED,
            status="started",
        )

        try:
            # Get recipe data (use user_edits if present, otherwise parsed_recipe)
            recipe_data = item.user_edits or item.parsed_recipe
            if not recipe_data:
                item.status = "failed"
                item.error_message = "No recipe data available"
                self.database.db.commit()
                return success({"error": "No recipe data", "item_id": item_id})

            # efi-3 — carry the extractor's inferred_fields list onto
            # the new Recipe via the allow-list-and-dedupe helper.
            # user_edits (when present) is the user's post-Review
            # payload; Review Import mutates its local copy of the list
            # on edit, so reading the field off recipe_data gives the
            # already-shrunk state.
            deduped_inferred = _filter_inferred_fields(
                recipe_data.get("inferred_fields")
            )

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
                primary_vibe=recipe_data.get("primary_vibe"),
                secondary_vibe=recipe_data.get("secondary_vibe"),
                inferred_fields=deduped_inferred,
                recipe_book_id=job.recipe_book_id,
            )
            self.database.create(recipe)
            self.database.db.refresh(recipe)

            # Source-photo promotion (FR87): when the extractor didn't
            # supply a hero image, copy the user-uploaded source photo
            # from parser-inputs to a permanent recipe-photos/ key and
            # use that URL. Best-effort — any failure leaves image_url
            # None and recipe creation still succeeds.
            self._maybe_promote_source_photo(recipe, item, job)

            # Create RecipeIngredient records
            ingredients_data = recipe_data.get("ingredients", [])
            for idx, ing_data in enumerate(ingredients_data):
                self._create_recipe_ingredient(recipe, ing_data, idx)

            # Create RecipeStep records from steps array
            steps_data = recipe_data.get("steps", [])
            if steps_data:
                for step_data in steps_data:
                    clean_timers, dropped = _clamp_timers(
                        step_data.get("timers")
                    )
                    if dropped > 0:
                        _log_timer_clamp(
                            self.database.db,
                            recipe_name=recipe.name,
                            step_order=step_data.get("order", 1),
                            dropped_count=dropped,
                            raw_input=step_data.get("timers"),
                        )
                    step = RecipeStep(
                        recipe_id=recipe.id,
                        step_number=step_data.get("order", 1),
                        instruction=step_data.get("instruction", ""),
                        timers=clean_timers,
                    )
                    self.database.create(step)
            elif recipe_data.get("instructions"):
                # Fallback: split instructions string into steps
                instructions = recipe_data["instructions"]
                import re
                raw_steps = re.split(r'\d+\.\s+', instructions)
                raw_steps = [s.strip() for s in raw_steps if s.strip()]
                for idx, step_text in enumerate(raw_steps):
                    step = RecipeStep(
                        recipe_id=recipe.id,
                        step_number=idx + 1,
                        instruction=step_text,
                    )
                    self.database.create(step)

            # Update import item
            item.status = "completed"
            item.created_recipe_id = recipe.id
            self.database.db.commit()

            # Update job counts
            self._update_job_counts(job)

            # Stage-transition audit (irrd-2): recipe row persisted — the
            # terminal stage of the import pipeline.
            log_stage_transition(
                import_item_id=item.id,
                stage=STAGE_CREATED,
                status="ok",
            )

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
            log_stage_transition(
                import_item_id=item.id,
                stage=STAGE_CREATED,
                status="failed",
                error_message=str(e),
            )
            return success({"error": str(e), "item_id": item_id})

    def _maybe_promote_source_photo(
        self, recipe: Recipe, item: ImportItem, job: ImportJob
    ) -> None:
        """Promote the source photo to the recipe hero if no hero is set.

        Conditions (both required):
          * `recipe.image_url` is empty (the extractor didn't supply one), AND
          * `item.raw_data['s3_keys']` is a non-empty list (a photo import).

        The first key wins — multi-page recipes get their first page as
        hero in v1. On success, commits the new URL to `recipe.image_url`.
        Any failure is logged and left as a no-op; recipe creation is
        never blocked by a failed promotion.
        """
        if recipe.image_url:
            return
        s3_keys = (item.raw_data or {}).get("s3_keys") or []
        if not s3_keys:
            return
        try:
            aws = _get_aws_service()
            url = promote_source_photo(
                aws,
                user_id=job.user_id,
                recipe_id=recipe.id,
                source_s3_key=s3_keys[0],
                region=AWS_REGION,
                bucket=PARSER_INPUTS_BUCKET,
            )
        except Exception:
            logger.warning(
                "Source-photo promotion raised unexpectedly for recipe %s",
                recipe.id,
                exc_info=True,
            )
            return
        if url:
            recipe.image_url = url
            self.database.db.commit()
            logger.info(
                "Promoted source photo for recipe %s: %s -> %s",
                recipe.id,
                s3_keys[0],
                url,
            )

    def _create_recipe_ingredient(self, recipe: Recipe, ing_data: dict, order_index: int):
        """Create a RecipeIngredient record.

        Every parsed ingredient yields a fresh `ingredients` row — no
        find-or-create, no cross-recipe identity (see
        `epic-ingredients-string-simplification`).
        """
        raw_name = (
            ing_data.get("name")
            or ing_data.get("text")
            or "Unknown ingredient"
        )
        canonical = raw_name.strip().lower() or "unknown ingredient"
        ingredient = Ingredient(canonical_name=canonical)
        self.database.db.add(ingredient)
        self.database.db.flush()
        ingredient_id = str(ingredient.id)

        # Parse quantity
        quantity = ing_data.get("quantity")
        if quantity is not None:
            try:
                quantity = Decimal(str(quantity))
            except (ValueError, TypeError):
                quantity = Decimal("1")
        else:
            quantity = Decimal("1")

        # Coerce LLM/user freeform unit to the canonical token (riip-2).
        unit = normalize_unit_display(
            ing_data.get("unit") or "",
            self.database.db,
            context={"path": "create_recipe_task"},
        ) or ""

        # Normalize quantity if possible
        try:
            normalized = normalize_quantity(float(quantity), unit)
            quantity_normalized = Decimal(str(normalized.quantity_normalized))
            unit_normalized = normalized.unit_normalized
        except Exception:
            quantity_normalized = quantity
            unit_normalized = unit or ""

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

        previous_status = job.status

        # Cancelled is terminal and user-driven; never silently flip a
        # cancelled job back into a status that would fire IMPORT_FAILED
        # (sched-2) or any other user-visible transition.
        if previous_status == "cancelled":
            self.database.db.commit()
            return

        # Check if job is complete
        total_final = job.succeeded_items + job.failed_items + status_counts.get("skipped", 0)
        if total_final >= job.total_items:
            if (
                job.failed_items == job.total_items
                and job.total_items > 0
            ):
                # Every approved item failed to create. Mirror the
                # `extract_recipe_task` terminal branch so post-approval
                # failures surface the IMPORT_FAILED push.
                job.status = "failed"
            else:
                job.status = "completed"
            job.completed_at = datetime.now(UTC)
            # abi-2a: `import_complete` user_activity row no longer
            # written. The Imports tab shows completed items in the
            # green section; the bell (abi-1) excludes import_* types
            # via the Notifications-tab allow-list.
        elif job.pending_review_items > 0:
            job.status = "awaiting_review"

        self.database.db.commit()

        if (
            job.status == "awaiting_review"
            and previous_status != "awaiting_review"
        ):
            from utils.services.import_notifications import (
                notify_import_needs_review,
            )

            notify_import_needs_review(self.database, job)

        if (
            job.status == "failed"
            and previous_status != "failed"
        ):
            from utils.services.import_notifications import (
                notify_import_failed,
            )

            notify_import_failed(self.database, job)


# Register task with Celery
create_recipe_task = celery_app.register_task(CreateRecipeTask())
