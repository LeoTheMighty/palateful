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
        """Calculate comparison metrics between actual and expected recipes.

        Supports two input shapes transparently:
          * Legacy single-recipe: a bare recipe dict at the top level.
          * Multi-recipe: `{"recipes": [recipe_dict, ...]}` (FR88).

        Both are normalized to a list of recipes, then pair-wise compared
        using order-based alignment (`expected[i]` vs `actual[i]`). The
        rationale is documented with the workshop decision: extractors
        are instructed to emit recipes in source order, and expected
        fixtures are authored in the same order. If the model swaps
        order, the field_accuracy metric will drop and we'd upgrade to
        a name-similarity heuristic in a follow-up.
        """
        expected_list = self._normalize_to_recipe_list(expected)
        actual_list = self._normalize_to_recipe_list(actual)

        metrics: dict = {}

        # Recipe-count accuracy: binary per-case. 1.0 iff the extractor
        # returned the expected N; otherwise 0.0. Aggregated as a mean
        # over the suite (see runner._check_thresholds).
        metrics["recipe_count_accuracy"] = (
            1.0 if len(actual_list) == len(expected_list) else 0.0
        )
        metrics["expected_recipe_count"] = len(expected_list)
        metrics["actual_recipe_count"] = len(actual_list)

        if len(actual_list) != len(expected_list):
            # Emit a diagnostic so eval failures point at the count gap.
            import logging
            logging.getLogger(__name__).info(
                "alignment: expected N=%d actual N=%d; field metrics "
                "computed on first min(N) pairs",
                len(expected_list),
                len(actual_list),
            )

        # Pair-wise field/ingredient/instruction metrics on
        # min(N_expected, N_actual) pairs. Unpaired recipes on either
        # side contribute 0 to field_accuracy (counted as a whole
        # missed or hallucinated recipe). We aggregate with a weighted
        # mean so the numbers stay comparable across single- and
        # multi-recipe cases.
        paired = min(len(actual_list), len(expected_list))
        pair_metrics: list[dict] = []
        for i in range(paired):
            pair_metrics.append(
                self._single_recipe_metrics(actual_list[i], expected_list[i])
            )

        # Unpaired on either side: a missed expected recipe or a
        # hallucinated actual recipe each counts as 0 field_accuracy.
        unpaired_penalty_count = abs(len(actual_list) - len(expected_list))

        if not pair_metrics and unpaired_penalty_count == 0:
            # Degenerate: neither side has any recipes — pass trivially.
            metrics.update(
                field_accuracy=1.0,
                fields_correct=0,
                fields_total=0,
                missing_fields=[],
                extra_fields=[],
                ingredient_count_accuracy=1.0,
                instruction_similarity=1.0,
            )
            return metrics

        total_pairs = paired + unpaired_penalty_count

        def _avg(key: str) -> float:
            if not pair_metrics:
                return 0.0 if unpaired_penalty_count else 0.0
            numer = sum(p[key] for p in pair_metrics)
            # Denominator is total_pairs so unpaired recipes pull the
            # metric down (each contributes 0 to the numerator).
            return numer / total_pairs if total_pairs else 0.0

        metrics["field_accuracy"] = _avg("field_accuracy")
        metrics["ingredient_count_accuracy"] = _avg("ingredient_count_accuracy")
        metrics["instruction_similarity"] = _avg("instruction_similarity")

        # Keep the first pair's structural breakdown for quick debugging.
        if pair_metrics:
            first = pair_metrics[0]
            metrics["fields_correct"] = first["fields_correct"]
            metrics["fields_total"] = first["fields_total"]
            metrics["missing_fields"] = first["missing_fields"]
            metrics["extra_fields"] = first["extra_fields"]

        return metrics

    def _normalize_to_recipe_list(self, data: dict) -> list[dict]:
        """Normalize either a single-recipe dict or `{"recipes": [...]}`
        into a list of recipe dicts. Non-dict list entries are dropped.
        """
        recipes = data.get("recipes") if isinstance(data, dict) else None
        if isinstance(recipes, list):
            return [r for r in recipes if isinstance(r, dict)]
        # Fall through: treat the dict itself as a single recipe only if
        # it has recipe-shaped fields. An empty/error dict normalizes to
        # an empty list so len() comparisons remain meaningful.
        if isinstance(data, dict) and any(
            k in data for k in ("name", "ingredients", "instructions")
        ):
            return [data]
        return []

    def _single_recipe_metrics(self, actual: dict, expected: dict) -> dict:
        """Compute per-recipe metrics for one paired (actual, expected)."""
        m: dict = {}

        field_results = StructMetrics.compare_fields(actual, expected)
        m["field_accuracy"] = field_results["accuracy"]
        m["fields_correct"] = field_results["correct"]
        m["fields_total"] = field_results["total"]
        m["missing_fields"] = field_results["missing"]
        m["extra_fields"] = field_results["extra"]

        actual_ing_count = len(actual.get("ingredients", []))
        expected_ing_count = len(expected.get("ingredients", []))
        if expected_ing_count > 0:
            m["ingredient_count_accuracy"] = (
                min(actual_ing_count, expected_ing_count) / expected_ing_count
            )
        else:
            m["ingredient_count_accuracy"] = 1.0 if actual_ing_count == 0 else 0.0

        actual_instructions = actual.get("instructions", "") or ""
        expected_instructions = expected.get("instructions", "") or ""
        if expected_instructions:
            m["instruction_similarity"] = TextMetrics.normalized_levenshtein(
                actual_instructions, expected_instructions
            )
        else:
            m["instruction_similarity"] = 1.0 if not actual_instructions else 0.0

        return m
