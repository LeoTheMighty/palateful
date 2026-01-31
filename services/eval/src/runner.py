"""Evaluation orchestration runner."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import EvalConfig
from src.evaluators.base import BaseEvaluator, EvalResult

console = Console()


@dataclass
class SuiteResult:
    """Results for a single evaluation suite."""

    suite_name: str
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    results: list[EvalResult] = field(default_factory=list)
    metrics_summary: dict[str, float] = field(default_factory=dict)
    passed_threshold: bool = True
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "skipped_cases": self.skipped_cases,
            "results": [r.to_dict() for r in self.results],
            "metrics_summary": self.metrics_summary,
            "passed_threshold": self.passed_threshold,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SuiteResult":
        return cls(
            suite_name=data["suite_name"],
            total_cases=data["total_cases"],
            passed_cases=data["passed_cases"],
            failed_cases=data["failed_cases"],
            skipped_cases=data["skipped_cases"],
            results=[EvalResult.from_dict(r) for r in data["results"]],
            metrics_summary=data["metrics_summary"],
            passed_threshold=data["passed_threshold"],
            duration_seconds=data["duration_seconds"],
        )


@dataclass
class EvalResults:
    """Aggregated results from all evaluation suites."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    suite_results: dict[str, SuiteResult] = field(default_factory=dict)
    total_duration_seconds: float = 0.0
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "suite_results": {k: v.to_dict() for k, v in self.suite_results.items()},
            "total_duration_seconds": self.total_duration_seconds,
            "config_snapshot": self.config_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalResults":
        return cls(
            timestamp=data["timestamp"],
            suite_results={k: SuiteResult.from_dict(v) for k, v in data["suite_results"].items()},
            total_duration_seconds=data["total_duration_seconds"],
            config_snapshot=data.get("config_snapshot", {}),
        )


class EvalRunner:
    """Orchestrates evaluation runs across multiple suites."""

    def __init__(self, config: EvalConfig):
        self.config = config
        self._evaluators: dict[str, BaseEvaluator] = {}

    def _get_evaluator(self, suite: str) -> BaseEvaluator:
        """Get or create evaluator for a suite."""
        if suite not in self._evaluators:
            if suite == "ocr":
                from src.evaluators.ocr_evaluator import OCREvaluator
                self._evaluators[suite] = OCREvaluator(self.config)
            elif suite == "recipe_extraction":
                from src.evaluators.recipe_extraction_evaluator import RecipeExtractionEvaluator
                self._evaluators[suite] = RecipeExtractionEvaluator(self.config)
            elif suite == "ingredient_matching":
                from src.evaluators.ingredient_matching_evaluator import IngredientMatchingEvaluator
                self._evaluators[suite] = IngredientMatchingEvaluator(self.config)
            else:
                raise ValueError(f"Unknown suite: {suite}")
        return self._evaluators[suite]

    def run(self, suites: list[str]) -> EvalResults:
        """Run evaluations for the specified suites.

        Args:
            suites: List of suite names to run.

        Returns:
            Aggregated evaluation results.
        """
        start_time = time.time()
        results = EvalResults(
            config_snapshot={
                "mock_ai": self.config.mock_ai,
                "cache_responses": self.config.cache_responses,
                "parallel_workers": self.config.parallel_workers,
                "ocr_mode": self.config.ocr_mode,
            }
        )

        for suite in suites:
            suite_result = self._run_suite(suite)
            results.suite_results[suite] = suite_result

        results.total_duration_seconds = time.time() - start_time
        return results

    def _run_suite(self, suite: str) -> SuiteResult:
        """Run evaluation for a single suite."""
        evaluator = self._get_evaluator(suite)
        cases = evaluator.load_cases()

        # Apply tag filters
        if self.config.only_tags:
            cases = [c for c in cases if any(t in c.tags for t in self.config.only_tags)]
        if self.config.skip_tags:
            cases = [c for c in cases if not any(t in c.tags for t in self.config.skip_tags)]

        suite_result = SuiteResult(
            suite_name=suite,
            total_cases=len(cases),
        )

        if not cases:
            console.print(f"[yellow]No cases found for suite: {suite}[/yellow]")
            return suite_result

        start_time = time.time()

        # Run evaluations
        if self.config.parallel_workers > 1 and len(cases) > 1:
            suite_result.results = self._run_parallel(evaluator, cases)
        else:
            suite_result.results = self._run_sequential(evaluator, cases)

        suite_result.duration_seconds = time.time() - start_time

        # Calculate summary
        for result in suite_result.results:
            if result.skipped:
                suite_result.skipped_cases += 1
            elif result.passed:
                suite_result.passed_cases += 1
            else:
                suite_result.failed_cases += 1

        # Calculate aggregate metrics
        suite_result.metrics_summary = self._calculate_metrics_summary(suite_result.results)

        # Check thresholds
        suite_result.passed_threshold = self._check_thresholds(suite, suite_result.metrics_summary)

        return suite_result

    def _run_sequential(self, evaluator: BaseEvaluator, cases: list) -> list[EvalResult]:
        """Run cases sequentially with progress display."""
        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {evaluator.name}...", total=len(cases))

            for case in cases:
                progress.update(task, description=f"Running {evaluator.name}: {case.id}")
                result = evaluator.evaluate(case)
                results.append(result)
                progress.advance(task)

        return results

    def _run_parallel(self, evaluator: BaseEvaluator, cases: list) -> list[EvalResult]:
        """Run cases in parallel."""
        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {evaluator.name} (parallel)...", total=len(cases))

            with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
                future_to_case = {executor.submit(evaluator.evaluate, case): case for case in cases}

                for future in as_completed(future_to_case):
                    case = future_to_case[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append(EvalResult(
                            case_id=case.id,
                            passed=False,
                            error=str(e),
                        ))
                    progress.advance(task)

        return results

    def _calculate_metrics_summary(self, results: list[EvalResult]) -> dict[str, float]:
        """Calculate aggregate metrics from individual results."""
        if not results:
            return {}

        # Collect all metrics across results
        all_metrics: dict[str, list[float]] = {}
        for result in results:
            if result.skipped:
                continue
            for key, value in result.metrics.items():
                if isinstance(value, int | float):
                    all_metrics.setdefault(key, []).append(float(value))

        # Calculate averages
        summary = {}
        for key, values in all_metrics.items():
            if values:
                summary[f"{key}_avg"] = sum(values) / len(values)
                summary[f"{key}_min"] = min(values)
                summary[f"{key}_max"] = max(values)

        return summary

    def _check_thresholds(self, suite: str, metrics: dict[str, float]) -> bool:
        """Check if metrics meet configured thresholds."""
        thresholds = self.config.thresholds

        if suite == "ocr":
            char_acc = metrics.get("character_accuracy_avg", 0)
            return char_acc >= thresholds.ocr_character_accuracy
        elif suite == "recipe_extraction":
            field_acc = metrics.get("field_accuracy_avg", 0)
            return field_acc >= thresholds.recipe_field_accuracy
        elif suite == "ingredient_matching":
            match_rate = metrics.get("exact_match_rate_avg", 0)
            return match_rate >= thresholds.ingredient_match_rate

        return True

    def compare_results(self, current: EvalResults, baseline_path: Path) -> None:
        """Compare current results with a baseline."""
        with open(baseline_path) as f:
            baseline_data = json.load(f)
        baseline = EvalResults.from_dict(baseline_data)

        console.print("\n[bold]Comparison with Baseline[/bold]")
        console.print("-" * 50)

        for suite_name, current_suite in current.suite_results.items():
            baseline_suite = baseline.suite_results.get(suite_name)
            if not baseline_suite:
                console.print(f"[yellow]{suite_name}: No baseline data[/yellow]")
                continue

            console.print(f"\n[bold]{suite_name}[/bold]")

            # Compare key metrics
            for metric_key in current_suite.metrics_summary:
                if metric_key.endswith("_avg"):
                    current_val = current_suite.metrics_summary.get(metric_key, 0)
                    baseline_val = baseline_suite.metrics_summary.get(metric_key, 0)
                    diff = current_val - baseline_val

                    if diff > 0:
                        color = "green"
                        symbol = "+"
                    elif diff < 0:
                        color = "red"
                        symbol = ""
                    else:
                        color = "white"
                        symbol = ""

                    console.print(
                        f"  {metric_key}: {current_val:.4f} vs {baseline_val:.4f} "
                        f"([{color}]{symbol}{diff:.4f}[/{color}])"
                    )
