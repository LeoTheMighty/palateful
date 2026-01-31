"""Recipe extraction evaluator for HTML-to-recipe conversion."""

import json
from dataclasses import asdict

from src.config import EvalConfig
from src.evaluators.base import BaseEvaluator, EvalCase, EvalResult
from src.metrics.struct_metrics import StructMetrics
from src.metrics.text_metrics import TextMetrics


class RecipeExtractionEvaluator(BaseEvaluator):
    """Evaluates recipe extraction from HTML content."""

    name = "recipe_extraction"

    def __init__(self, config: EvalConfig):
        super().__init__(config)

    def load_cases(self) -> list[EvalCase]:
        """Load recipe extraction test cases from manifest."""
        manifest = self.load_manifest()
        cases = []

        for case_data in manifest.get("cases") or []:
            case_id = case_data["id"]
            html_path = self.suite_dir / case_data.get("html", f"html/{case_id}.html")
            expected_path = self.suite_dir / case_data.get("expected", f"expected/{case_id}.json")

            # Load expected JSON if available
            expected_data = None
            if expected_path.exists():
                with open(expected_path) as f:
                    expected_data = json.load(f)

            # Load HTML content
            html_content = None
            if html_path.exists():
                html_content = html_path.read_text(encoding="utf-8")

            cases.append(EvalCase(
                id=case_id,
                input_path=html_path,
                input_data=html_content,
                expected_path=expected_path,
                expected_data=expected_data,
                tags=case_data.get("tags", []),
                metadata={
                    "url": case_data.get("url"),
                    "extractor": case_data.get("extractor"),  # json_ld, ai, or auto
                    **case_data.get("metadata", {}),
                },
            ))

        return cases

    def evaluate(self, case: EvalCase) -> EvalResult:
        """Evaluate recipe extraction on a single HTML file."""
        result = EvalResult(case_id=case.id)

        # Check if input exists
        if not case.input_data:
            result.error = f"HTML content not found for case: {case.id}"
            return result

        # Check cache first
        cache_key = case.get_cache_key()
        cached = self.get_cached_response(cache_key)

        if cached is not None:
            result.actual_output = cached
            result.cache_hit = True
            result.cost_cents = cached.get("_cost_cents", 0)
        else:
            # Run extraction
            try:
                extractor_type = case.metadata.get("extractor", "auto")
                extracted, duration_ms, cost_cents = self._extract_recipe(
                    html=case.input_data,
                    url=case.metadata.get("url"),
                    extractor_type=extractor_type,
                )
                result.actual_output = extracted
                result.duration_ms = duration_ms
                result.cost_cents = cost_cents

                # Cache the response
                if extracted:
                    extracted["_cost_cents"] = cost_cents
                    self.save_cached_response(cache_key, extracted)
            except Exception as e:
                result.error = str(e)
                return result

        # If no expected output, just return the actual output
        if case.expected_data is None:
            result.passed = True
            result.metrics["note"] = "No expected output to compare"
            return result

        result.expected_output = case.expected_data

        # Calculate metrics
        if result.actual_output:
            metrics = self._calculate_metrics(result.actual_output, case.expected_data)
            result.metrics = metrics

            # Determine pass/fail based on field accuracy
            field_accuracy = metrics.get("field_accuracy", 0)
            result.passed = field_accuracy >= self.config.thresholds.recipe_field_accuracy
        else:
            result.passed = False
            result.metrics["field_accuracy"] = 0.0

        return result

    def _extract_recipe(
        self,
        html: str,
        url: str | None,
        extractor_type: str,
    ) -> tuple[dict | None, float, int]:
        """Extract recipe from HTML content.

        Args:
            html: HTML content to extract from.
            url: Source URL (optional).
            extractor_type: Type of extractor to use (json_ld, ai, auto).

        Returns:
            Tuple of (extracted_recipe_dict, duration_ms, cost_cents)
        """
        if self.config.mock_ai and extractor_type == "ai":
            # Return None in mock mode for AI extraction if no cache
            return None, 0.0, 0

        # Import production extractors
        from utils.services.recipe_extractors.ai_extractor import AIExtractor
        from utils.services.recipe_extractors.json_ld import JsonLdExtractor

        cost_cents = 0
        extracted = None
        duration_ms = 0.0

        if extractor_type == "json_ld" or extractor_type == "auto":
            # Try JSON-LD first
            json_ld = JsonLdExtractor()
            result, duration_ms = self.timed_execution(json_ld.extract, html, url)

            if result.success and result.recipe:
                extracted = self._recipe_to_dict(result.recipe)
                cost_cents = result.ai_cost_cents

        if extracted is None and (extractor_type == "ai" or extractor_type == "auto"):
            # Fall back to AI extraction
            if not self.config.mock_ai:
                ai_extractor = AIExtractor()
                result, duration_ms = self.timed_execution(ai_extractor.extract, html, url)

                if result.success and result.recipe:
                    extracted = self._recipe_to_dict(result.recipe)
                    cost_cents = result.ai_cost_cents

        return extracted, duration_ms, cost_cents

    def _recipe_to_dict(self, recipe) -> dict:
        """Convert ExtractedRecipe to a plain dict."""
        if hasattr(recipe, "__dict__"):
            result = {}
            for key, value in recipe.__dict__.items():
                if key.startswith("_"):
                    continue
                if hasattr(value, "__dict__"):
                    result[key] = asdict(value) if hasattr(value, "__dataclass_fields__") else str(value)
                elif isinstance(value, list):
                    result[key] = [
                        asdict(item) if hasattr(item, "__dataclass_fields__") else item
                        for item in value
                    ]
                else:
                    result[key] = value
            return result
        return dict(recipe) if isinstance(recipe, dict) else {}

    def _calculate_metrics(self, actual: dict, expected: dict) -> dict:
        """Calculate comparison metrics between actual and expected recipes."""
        metrics = {}

        # Field-level comparison
        field_results = StructMetrics.compare_fields(actual, expected)
        metrics["field_accuracy"] = field_results["accuracy"]
        metrics["fields_correct"] = field_results["correct"]
        metrics["fields_total"] = field_results["total"]
        metrics["missing_fields"] = field_results["missing"]
        metrics["extra_fields"] = field_results["extra"]

        # Ingredient count comparison
        actual_ing_count = len(actual.get("ingredients", []))
        expected_ing_count = len(expected.get("ingredients", []))
        if expected_ing_count > 0:
            metrics["ingredient_count_accuracy"] = min(actual_ing_count, expected_ing_count) / expected_ing_count
        else:
            metrics["ingredient_count_accuracy"] = 1.0 if actual_ing_count == 0 else 0.0

        # Instruction similarity (if both have instructions)
        actual_instructions = actual.get("instructions", "") or ""
        expected_instructions = expected.get("instructions", "") or ""
        if expected_instructions:
            metrics["instruction_similarity"] = TextMetrics.normalized_levenshtein(
                actual_instructions, expected_instructions
            )
        else:
            metrics["instruction_similarity"] = 1.0 if not actual_instructions else 0.0

        return metrics
