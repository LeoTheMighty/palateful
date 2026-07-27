"""Vision extraction evaluator for image-to-recipe conversion (bugs-imp-pho-7).

The text suite (`recipe_extraction`) grades HTML -> recipe. This suite grades
the vision path — `extract_recipe_from_image` (gpt-4o-mini) — against the
image fixtures under `fixtures/images/`, using the *same* metric and
alignment code as the text suite.

Reuse, not duplication: this evaluator subclasses `RecipeExtractionEvaluator`
so `_calculate_metrics`, `_normalize_to_recipe_list`, `_single_recipe_metrics`
and the order-based alignment (plus its alignment-fallback log line) are
shared verbatim. Only case loading (images instead of HTML) and the
extraction call differ.

Cost: every non-cached case is a live gpt-4o-mini vision call. In
`mock_ai` mode a case with no cached response is *skipped* rather than
billed, so the suite is safe to run without an API key.
"""

import json
import logging

from src.config import EvalConfig
from src.evaluators.base import EvalCase, EvalResult
from src.evaluators.recipe_extraction_evaluator import RecipeExtractionEvaluator
from src.metrics.unit_enum_compliance import compute_unit_enum_compliance

logger = logging.getLogger(__name__)

# Cases carrying this tag are the ones the recipe_count_accuracy gate
# really cares about — a single-recipe photo scores 1.0 almost for free,
# so they'd dilute the suite-wide average. Multi-tagged cases also emit
# `multi_recipe_count_accuracy` and are gated separately in
# runner._check_thresholds.
MULTI_RECIPE_TAG = "multi_recipe"


class VisionExtractionEvaluator(RecipeExtractionEvaluator):
    """Evaluates recipe extraction from photos of recipes."""

    name = "vision_extraction"

    def __init__(self, config: EvalConfig):
        super().__init__(config)

    def load_cases(self) -> list[EvalCase]:
        """Load vision test cases from the manifest.

        Manifest keys (`image`, `expected`) are resolved relative to the
        suite dir, which lets a case point at the shared fixture tree
        (`../../fixtures/images/x.png`) so an image case and its text
        twin grade against one expected JSON.
        """
        manifest = self.load_manifest()
        cases: list[EvalCase] = []

        for case_data in manifest.get("cases") or []:
            case_id = case_data["id"]
            image_path = self._resolve(case_data.get("image", f"images/{case_id}.png"))
            expected_path = self._resolve(
                case_data.get("expected", f"expected/{case_id}.json")
            )

            expected_data = None
            if expected_path.exists():
                with open(expected_path) as f:
                    expected_data = json.load(f)

            cases.append(EvalCase(
                id=case_id,
                input_path=image_path,
                # Deliberately left unset: EvalCase.get_cache_key() hashes
                # input_path's bytes, and holding every PNG in memory for
                # the whole run buys nothing.
                input_data=None,
                expected_path=expected_path,
                expected_data=expected_data,
                tags=case_data.get("tags", []),
                metadata=dict(case_data.get("metadata", {})),
            ))

        return cases

    def _resolve(self, relative: str):
        """Resolve a manifest-relative path (may contain `../`)."""
        return (self.suite_dir / relative).resolve()

    def evaluate(self, case: EvalCase) -> EvalResult:
        """Evaluate vision extraction on a single image fixture."""
        result = EvalResult(case_id=case.id)

        if case.input_path is None or not case.input_path.exists():
            result.error = f"Image not found for case: {case.id}"
            return result

        cache_key = case.get_cache_key()
        cached = self.get_cached_response(cache_key)

        if cached is not None:
            result.actual_output = cached
            result.cache_hit = True
            result.cost_cents = cached.get("_cost_cents", 0)
        elif self.config.mock_ai:
            # Cost guard: never bill a live vision call in mock mode.
            result.skipped = True
            result.metrics["note"] = "mock_ai enabled and no cached response"
            return result
        else:
            try:
                extracted, duration_ms, cost_cents, succeeded = self._extract_from_image(
                    case.input_path
                )
                result.actual_output = extracted
                result.duration_ms = duration_ms
                result.cost_cents = cost_cents

                # Only a *successful* extraction is worth remembering. A
                # failure still grades 0.0 for this run, but caching it
                # would make every later mock re-grade replay a zero that
                # was really a missing key or a transient API error —
                # indistinguishable from a genuine model miss.
                if extracted and succeeded:
                    extracted["_cost_cents"] = cost_cents
                    self.save_cached_response(cache_key, extracted)
            except Exception as e:
                result.error = str(e)
                return result

        if case.expected_data is None:
            result.passed = True
            result.metrics["note"] = "No expected output to compare"
            return result

        result.expected_output = case.expected_data

        if result.actual_output:
            # Identical metric/alignment code as the text suite.
            metrics = self._calculate_metrics(result.actual_output, case.expected_data)
            metrics["unit_enum_compliance"] = compute_unit_enum_compliance(
                result.actual_output
            )
        else:
            metrics = {
                "field_accuracy": 0.0,
                "recipe_count_accuracy": 0.0,
                "expected_recipe_count": len(
                    self._normalize_to_recipe_list(case.expected_data)
                ),
                "actual_recipe_count": 0,
            }

        if MULTI_RECIPE_TAG in case.tags:
            # Mirror the count metric under a tag-scoped key so the gate
            # can grade fan-out without single-recipe cases padding it.
            metrics["multi_recipe_count_accuracy"] = metrics["recipe_count_accuracy"]

        result.metrics = metrics
        # field_accuracy stays the per-case pass/fail signal, matching the
        # text suite; the suite-level hard gate is recipe_count_accuracy
        # (see runner._check_thresholds) while a field_accuracy baseline
        # is being collected.
        result.passed = (
            metrics.get("field_accuracy", 0.0)
            >= self.config.thresholds.recipe_field_accuracy
        )

        return result

    def _extract_from_image(self, image_path) -> tuple[dict | None, float, int, bool]:
        """Run the production vision extractor against one image file.

        Returns:
            Tuple of (extracted_dict_or_None, duration_ms, cost_cents,
            succeeded). The dict is always the multi-recipe shape
            (`{"recipes": [...]}`) so it feeds `_calculate_metrics`
            unchanged. `succeeded` mirrors `ExtractionResult.success` and
            gates caching — see `evaluate`.
        """
        from utils.services.recipe_extractors.vision_extractor import (
            extract_recipe_from_image,
        )

        image_bytes = image_path.read_bytes()
        extraction, duration_ms = self.timed_execution(
            extract_recipe_from_image, image_bytes
        )

        cost_cents = getattr(extraction, "ai_cost_cents", 0) or 0

        if not extraction.success:
            logger.info(
                "vision extraction failed for %s: %s (%s)",
                image_path.name,
                extraction.error_message,
                extraction.error_code,
            )
            # A failed extraction is a real miss, not an infra error: fall
            # through with an empty recipe list so recipe_count_accuracy
            # scores 0 instead of the case erroring out of the average.
            # It is *not* cached — the caller drops it.
            return {"recipes": []}, duration_ms, cost_cents, False

        # Post pho-1 the extractor returns `recipes`; `recipe` is a
        # deprecated alias and is intentionally not read here.
        recipes = [self._recipe_to_dict(r) for r in (extraction.recipes or [])]
        return {"recipes": recipes}, duration_ms, cost_cents, True
