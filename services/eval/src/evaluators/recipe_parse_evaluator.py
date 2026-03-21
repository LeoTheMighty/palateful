"""Recipe parse evaluator — tests that recipe URLs and OCR produce correct structured recipes.

Uses LLM-as-judge to determine correctness of parsed recipe fields.
Loads QA pairs from datasets/recipe_parse/qa_pairs.json.
"""

import json

from src.bridge import run_parser_trial
from src.config import EvalConfig
from src.evaluators.base import BaseEvaluator, EvalCase, EvalResult
from src.judge import judge
from src.results import CaseSummary, TrialRecord


class RecipeParseEvaluator(BaseEvaluator):
    """Evaluates recipe parsing from URLs and OCR text using LLM-as-judge."""

    name = "recipe_parse"

    def __init__(self, config: EvalConfig):
        super().__init__(config)

    def load_cases(self) -> list[EvalCase]:
        """Load QA pairs from the recipe_parse dataset."""
        qa_path = self.suite_dir / "qa_pairs.json"
        if not qa_path.exists():
            return []

        with open(qa_path) as f:
            qa_pairs = json.load(f)

        cases = []
        for i, pair in enumerate(qa_pairs):
            case_id = pair.get("id", f"recipe_parse_{i}")
            cases.append(EvalCase(
                id=case_id,
                input_data={
                    "input_type": pair.get("input_type", "html"),
                    "input_url": pair.get("input_url"),
                    "input_html": pair.get("input_html"),
                },
                expected_data=pair.get("expected", {}),
                tags=pair.get("tags", []),
                metadata={
                    "query_type": pair.get("query_type", "recipe_parse"),
                    "repeats": pair.get("repeats"),
                },
            ))

        return cases

    def evaluate(self, case: EvalCase) -> EvalResult:
        """Evaluate a single recipe parse case.

        Runs the parser, then uses LLM-as-judge to compare output to expected.
        """
        result = EvalResult(case_id=case.id)

        if not case.input_data:
            result.error = "No input data for case"
            return result

        input_data = case.input_data
        expected = case.expected_data or {}

        # Check cache
        cache_key = case.get_cache_key()
        cached = self.get_cached_response(cache_key)

        if cached is not None:
            result.actual_output = cached.get("output")
            result.cache_hit = True
            judge_result = cached.get("judge_result", {})
            result.passed = judge_result.get("is_correct", False)
            result.metrics = cached.get("metrics", {})
            return result

        # Run parser trial
        trial = run_parser_trial(
            input_type=input_data.get("input_type", "html"),
            input_html=input_data.get("input_html"),
            input_url=input_data.get("input_url"),
        )

        result.duration_ms = trial.duration_ms

        if trial.error:
            result.error = trial.error
            result.passed = False
            return result

        result.actual_output = trial.output
        result.expected_output = expected

        # Use LLM-as-judge
        try:
            judgment = judge(
                query_type="recipe_parse",
                actual=trial.output,
                expected=expected,
                model=self.config.judge_model if hasattr(self.config, "judge_model") else None,
            )
            result.passed = judgment.is_correct
            result.metrics = {
                "judge_reasoning": judgment.reasoning,
                "duration_ms": trial.duration_ms,
            }

            # Also compute deterministic field-level metrics
            if trial.output and isinstance(trial.output, dict):
                result.metrics.update(self._compute_field_metrics(trial.output, expected))

        except Exception as e:
            # Fall back to deterministic comparison if judge fails
            result.metrics["judge_error"] = str(e)
            if trial.output and isinstance(trial.output, dict):
                field_metrics = self._compute_field_metrics(trial.output, expected)
                result.metrics.update(field_metrics)
                result.passed = field_metrics.get("field_accuracy", 0) >= 0.6
            else:
                result.passed = False

        # Cache the result
        self.save_cached_response(cache_key, {
            "output": trial.output,
            "judge_result": {"is_correct": result.passed, "reasoning": result.metrics.get("judge_reasoning", "")},
            "metrics": result.metrics,
        })

        return result

    def evaluate_with_repeats(self, case: EvalCase, repeats: int = 1) -> CaseSummary:
        """Run multiple trials for a single case and aggregate results.

        Args:
            case: The eval case.
            repeats: Number of trials to run.

        Returns:
            CaseSummary with trial-level records.
        """
        summary = CaseSummary(
            case_id=case.id,
            query_type="recipe_parse",
        )

        for trial_num in range(1, repeats + 1):
            result = self.evaluate(case)
            summary.trials.append(TrialRecord(
                case_id=case.id,
                trial_number=trial_num,
                query_type="recipe_parse",
                passed=result.passed,
                reasoning=result.metrics.get("judge_reasoning", ""),
                duration_ms=result.duration_ms,
                error=result.error,
            ))

        summary.compute()
        return summary

    @staticmethod
    def _compute_field_metrics(actual: dict, expected: dict) -> dict:
        """Compute deterministic field-level accuracy metrics."""
        fields_to_check = ["name", "prep_time", "cook_time", "servings", "ingredient_count", "step_count"]

        correct = 0
        total = 0

        for field_name in fields_to_check:
            if field_name not in expected:
                continue
            total += 1
            exp_val = expected[field_name]
            act_val = actual.get(field_name)

            if act_val is None:
                continue

            if isinstance(exp_val, str) and isinstance(act_val, str):
                if exp_val.lower().strip() == act_val.lower().strip():
                    correct += 1
            elif isinstance(exp_val, int | float) and isinstance(act_val, int | float):
                # Allow tolerance of 2 for counts, 5 for times
                tolerance = 5 if "time" in field_name else 2
                if abs(exp_val - act_val) <= tolerance:
                    correct += 1
            elif exp_val == act_val:
                correct += 1

        return {
            "field_accuracy": correct / total if total > 0 else 0.0,
            "fields_correct": correct,
            "fields_total": total,
        }
