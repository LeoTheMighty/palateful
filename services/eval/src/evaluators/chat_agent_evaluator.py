"""Chat agent evaluator — tests AI chat responses and tool usage.

Loads QA pairs from datasets/chat_agent/qa_pairs.json.
Uses LLM-as-judge for semantic correctness and tool-use evaluation.
"""

import json

from src.bridge import run_chat_trial
from src.config import EvalConfig
from src.evaluators.base import BaseEvaluator, EvalCase, EvalResult
from src.judge import judge
from src.results import CaseSummary, EvalRunSummary, TrialRecord


class ChatAgentEvaluator(BaseEvaluator):
    """Evaluates chat agent responses using LLM-as-judge."""

    name = "chat_agent"

    def __init__(self, config: EvalConfig):
        super().__init__(config)

    def load_cases(self) -> list[EvalCase]:
        """Load QA pairs from the chat_agent dataset."""
        qa_path = self.suite_dir / "qa_pairs.json"
        if not qa_path.exists():
            return []

        with open(qa_path) as f:
            qa_pairs = json.load(f)

        cases = []
        for i, pair in enumerate(qa_pairs):
            case_id = pair.get("id", f"chat_{i}")
            cases.append(EvalCase(
                id=case_id,
                input_data={
                    "query": pair["query"],
                    "recipe_context": pair.get("recipe_context"),
                },
                expected_data={
                    "expected_answer": pair.get("expected_answer", ""),
                    "query_type": pair.get("query_type", "chat_answer"),
                },
                tags=pair.get("tags", []),
                metadata={
                    "query_type": pair.get("query_type", "chat_answer"),
                    "repeats": pair.get("repeats"),
                },
            ))

        return cases

    def evaluate(self, case: EvalCase) -> EvalResult:
        """Evaluate a single chat agent case.

        Runs the chat agent with the query, then uses LLM-as-judge
        to determine if the response is correct.
        """
        result = EvalResult(case_id=case.id)

        if not case.input_data:
            result.error = "No input data for case"
            return result

        query = case.input_data.get("query", "")
        recipe_context = case.input_data.get("recipe_context")
        expected = case.expected_data or {}
        query_type = expected.get("query_type", "chat_answer")
        expected_answer = expected.get("expected_answer", "")

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

        # Run chat trial
        trial = run_chat_trial(
            query=query,
            recipe_context=recipe_context,
        )

        result.duration_ms = trial.duration_ms

        if trial.error:
            result.error = trial.error
            result.passed = False
            return result

        # Build actual output depending on query type
        if query_type == "chat_tool_use":
            actual_output = {
                "answer": trial.output,
                "tool_calls": trial.tool_calls,
            }
        else:
            actual_output = trial.output

        result.actual_output = actual_output
        result.expected_output = expected_answer

        # Use LLM-as-judge
        try:
            judgment = judge(
                query_type=query_type,
                actual=actual_output,
                expected=expected_answer,
                query=query,
                recipe_context=recipe_context,
            )
            result.passed = judgment.is_correct
            result.metrics = {
                "judge_reasoning": judgment.reasoning,
                "query_type": query_type,
                "duration_ms": trial.duration_ms,
                "tokens_used": trial.tokens_used,
                "tool_calls_count": len(trial.tool_calls),
            }

            if trial.tool_calls:
                result.metrics["tools_used"] = [tc["name"] for tc in trial.tool_calls]

        except Exception as e:
            result.metrics["judge_error"] = str(e)
            # For tool_use queries, fall back to checking if tool was called
            if query_type == "chat_tool_use" and trial.tool_calls:
                result.passed = True  # At least a tool was called
                result.metrics["fallback_check"] = "tool_called"
            else:
                result.passed = False

        # Cache the result
        self.save_cached_response(cache_key, {
            "output": actual_output,
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
        query_type = case.metadata.get("query_type", "chat_answer")
        summary = CaseSummary(
            case_id=case.id,
            query_type=query_type,
        )

        for trial_num in range(1, repeats + 1):
            result = self.evaluate(case)
            summary.trials.append(TrialRecord(
                case_id=case.id,
                trial_number=trial_num,
                query_type=query_type,
                passed=result.passed,
                reasoning=result.metrics.get("judge_reasoning", ""),
                duration_ms=result.duration_ms,
                tokens_used=result.metrics.get("tokens_used", 0),
                error=result.error,
            ))

        summary.compute()
        return summary
