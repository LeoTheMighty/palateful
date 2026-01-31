"""Ingredient matching evaluator for text-to-ingredient ID matching."""

import yaml

from src.config import EvalConfig
from src.evaluators.base import BaseEvaluator, EvalCase, EvalResult


class IngredientMatchingEvaluator(BaseEvaluator):
    """Evaluates ingredient matching accuracy."""

    name = "ingredient_matching"

    def __init__(self, config: EvalConfig):
        super().__init__(config)
        self._db_session = None

    def load_cases(self) -> list[EvalCase]:
        """Load ingredient matching test cases from cases.yaml."""
        cases_path = self.suite_dir / "cases.yaml"
        if not cases_path.exists():
            return []

        with open(cases_path) as f:
            data = yaml.safe_load(f) or {}

        cases = []
        for case_data in data.get("cases") or []:
            cases.append(EvalCase(
                id=case_data.get("id", case_data.get("input", "")[:20]),
                input_data=case_data.get("input"),
                expected_data={
                    "ingredient_id": case_data.get("expected_id"),
                    "ingredient_name": case_data.get("expected_name"),
                    "match_type": case_data.get("expected_match_type"),
                    "min_confidence": case_data.get("min_confidence", 0.0),
                },
                tags=case_data.get("tags", []),
                metadata=case_data.get("metadata", {}),
            ))

        return cases

    def evaluate(self, case: EvalCase) -> EvalResult:
        """Evaluate ingredient matching for a single input."""
        result = EvalResult(case_id=case.id)

        if not case.input_data:
            result.error = "No input text provided"
            return result

        # Check cache first
        cache_key = case.get_cache_key()
        cached = self.get_cached_response(cache_key)

        if cached is not None:
            match_result = cached
            result.cache_hit = True
        else:
            # Run matching
            try:
                match_result, duration_ms = self._match_ingredient(case.input_data)
                result.duration_ms = duration_ms

                # Cache the response
                self.save_cached_response(cache_key, match_result)
            except Exception as e:
                result.error = str(e)
                return result

        result.actual_output = match_result

        # If no expected output, just return the result
        if case.expected_data is None or case.expected_data.get("ingredient_id") is None:
            result.passed = True
            result.metrics["note"] = "No expected output to compare"
            return result

        result.expected_output = case.expected_data

        # Calculate metrics
        metrics = self._calculate_metrics(match_result, case.expected_data)
        result.metrics = metrics

        # Determine pass/fail
        result.passed = metrics.get("exact_match", False) or (
            metrics.get("confidence", 0) >= case.expected_data.get("min_confidence", 0.85) and
            match_result.get("ingredient_id") is not None
        )

        return result

    def _match_ingredient(self, ingredient_text: str) -> tuple[dict, float]:
        """Match ingredient text to an existing ingredient.

        Returns:
            Tuple of (match_result_dict, duration_ms)
        """
        if self.config.mock_ai:
            # Return no match in mock mode if no cache
            return {
                "ingredient_id": None,
                "ingredient_name": None,
                "confidence": 0.0,
                "match_type": "none",
                "needs_review": True,
            }, 0.0

        # Use a simplified matching approach for evaluation
        # In production, this uses the full MatchIngredientsTask
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine(self.config.database_url)

        with Session(engine) as session:
            # Tier 1: Exact match
            result, duration = self.timed_execution(
                self._do_matching, session, ingredient_text
            )
            return result, duration

    def _do_matching(self, session, ingredient_text: str) -> dict:
        """Perform the actual matching logic."""
        from sqlalchemy import func, text
        from utils.models.ingredient import Ingredient

        normalized = ingredient_text.lower().strip()
        ingredient_name = self._extract_ingredient_name(normalized)

        # Tier 1: Exact match
        ingredient = session.query(Ingredient).filter(
            func.lower(Ingredient.canonical_name) == ingredient_name.lower()
        ).first()

        if ingredient:
            return {
                "ingredient_id": str(ingredient.id),
                "ingredient_name": ingredient.canonical_name,
                "confidence": 1.0,
                "match_type": "exact",
                "needs_review": False,
            }

        # Tier 2: Fuzzy match using pg_trgm
        try:
            result = session.execute(
                text("""
                    SELECT id, canonical_name, similarity(lower(canonical_name), :name) as sim
                    FROM ingredients
                    WHERE similarity(lower(canonical_name), :name) > 0.3
                    ORDER BY sim DESC
                    LIMIT 1
                """),
                {"name": ingredient_name.lower()}
            ).first()

            if result:
                confidence = float(result.sim)
                return {
                    "ingredient_id": str(result.id),
                    "ingredient_name": result.canonical_name,
                    "confidence": confidence,
                    "match_type": "fuzzy",
                    "needs_review": confidence < 0.85,
                }
        except Exception:
            pass  # pg_trgm might not be installed

        # No match
        return {
            "ingredient_id": None,
            "ingredient_name": None,
            "confidence": 0.0,
            "match_type": "none",
            "needs_review": True,
        }

    def _extract_ingredient_name(self, text: str) -> str:
        """Extract ingredient name from full ingredient text."""
        import re

        # Remove common quantity patterns
        text = re.sub(r"^\d+[\./]?\d*\s*", "", text)
        text = re.sub(
            r"^(cup|cups|tablespoon|tablespoons|tbsp|teaspoon|teaspoons|tsp|"
            r"ounce|ounces|oz|pound|pounds|lb|lbs|gram|grams|g|kg|ml|l|"
            r"clove|cloves|piece|pieces|can|cans|package|packages|bunch|bunches|"
            r"large|medium|small|whole|half|quarter|pinch|dash|to taste)\s+",
            "", text, flags=re.IGNORECASE
        )

        # Remove text in parentheses
        text = re.sub(r"\([^)]*\)", "", text)

        # Remove everything after comma
        text = re.sub(r",.*$", "", text)

        return text.strip()

    def _calculate_metrics(self, actual: dict, expected: dict) -> dict:
        """Calculate comparison metrics."""
        metrics = {}

        # Exact ID match
        actual_id = actual.get("ingredient_id")
        expected_id = expected.get("ingredient_id")
        metrics["exact_match"] = actual_id == expected_id if expected_id else False

        # Confidence
        metrics["confidence"] = actual.get("confidence", 0.0)

        # Match type
        metrics["match_type"] = actual.get("match_type", "none")
        metrics["expected_match_type"] = expected.get("match_type")

        # Name match (if provided)
        actual_name = (actual.get("ingredient_name") or "").lower()
        expected_name = (expected.get("ingredient_name") or "").lower()
        if expected_name:
            metrics["name_match"] = actual_name == expected_name

        # False positive check
        if expected_id is None and actual_id is not None:
            metrics["false_positive"] = True
        else:
            metrics["false_positive"] = False

        return metrics
