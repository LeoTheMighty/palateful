"""Fixture-based evaluation runner.

Scans the fixtures/ directory for input + expected pairs, runs the specified
extraction strategy, scores the results, and reports aggregate metrics.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from src.scoring import score_extraction
from src.strategies import STRATEGIES, get_strategy_function

logger = logging.getLogger(__name__)
console = Console()

# Supported input extensions per type
INPUT_TYPE_EXTENSIONS: dict[str, list[str]] = {
    "text": [".txt", ".md"],
    "image": [".jpg", ".jpeg", ".png", ".webp", ".heic"],
    "url": [".json"],  # URL configs are stored as JSON
}

# Map fixture sub-directory name to input type
DIR_TO_INPUT_TYPE: dict[str, str] = {
    "text": "text",
    "images": "image",
    "urls": "url",
}


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------

def _discover_fixtures(
    fixtures_dir: Path,
    input_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Find fixture pairs: input file + matching expected JSON.

    Convention: ``text/potato_quiche.txt`` matches ``expected/potato_quiche.json``
    (filenames without extension must match).

    Args:
        fixtures_dir: Root fixtures directory (e.g. ``services/eval/fixtures``).
        input_types: Restrict to these input types. ``None`` means all.

    Returns:
        List of dicts with keys: id, input_path, expected_path, input_type.
    """
    expected_dir = fixtures_dir / "expected"
    if not expected_dir.is_dir():
        return []

    # Index expected files by stem
    expected_by_stem: dict[str, Path] = {}
    for f in expected_dir.iterdir():
        if f.suffix == ".json":
            expected_by_stem[f.stem] = f

    fixtures: list[dict[str, Any]] = []

    for dir_name, input_type in DIR_TO_INPUT_TYPE.items():
        if input_types and input_type not in input_types:
            continue

        input_dir = fixtures_dir / dir_name
        if not input_dir.is_dir():
            continue

        valid_exts = INPUT_TYPE_EXTENSIONS.get(input_type, [])
        for input_file in sorted(input_dir.iterdir()):
            if input_file.name.startswith("."):
                continue
            if input_file.suffix.lower() not in valid_exts:
                continue

            stem = input_file.stem
            expected_path = expected_by_stem.get(stem)
            if expected_path is None:
                logger.warning("No expected JSON for fixture '%s', skipping", stem)
                continue

            fixtures.append({
                "id": stem,
                "input_path": input_file,
                "expected_path": expected_path,
                "input_type": input_type,
            })

    return fixtures


# ---------------------------------------------------------------------------
# Single-fixture evaluation
# ---------------------------------------------------------------------------

def _evaluate_fixture(
    fixture: dict[str, Any],
    strategy: str,
) -> dict[str, Any]:
    """Run extraction + scoring for a single fixture.

    Returns a result dict with:
        id, strategy, input_type, scores (from scoring.py),
        error (if any), duration_ms.
    """
    fixture_id = fixture["id"]
    input_path: Path = fixture["input_path"]
    expected_path: Path = fixture["expected_path"]
    input_type: str = fixture["input_type"]

    result: dict[str, Any] = {
        "id": fixture_id,
        "strategy": strategy,
        "input_type": input_type,
        "scores": {},
        "error": None,
        "duration_ms": 0.0,
    }

    # Load expected
    try:
        with open(expected_path) as f:
            expected = json.load(f)
    except Exception as e:
        result["error"] = f"Failed to load expected JSON: {e}"
        return result

    # Load input and run strategy
    try:
        strategy_fn = get_strategy_function(strategy)

        start = time.perf_counter()

        if input_type == "text":
            input_text = input_path.read_text(encoding="utf-8")
            extracted = strategy_fn(input_text)
        elif input_type == "image":
            extracted = strategy_fn(str(input_path))
        elif input_type == "url":
            with open(input_path) as f:
                url_config = json.load(f)
            extracted = strategy_fn(url_config.get("url", ""))
        else:
            raise ValueError(f"Unsupported input type: {input_type}")

        result["duration_ms"] = (time.perf_counter() - start) * 1000

    except NotImplementedError as e:
        result["error"] = str(e)
        return result
    except Exception as e:
        result["error"] = f"Extraction failed: {e}"
        return result

    # Score
    try:
        scores = score_extraction(extracted, expected)
        result["scores"] = scores
    except Exception as e:
        result["error"] = f"Scoring failed: {e}"

    return result


# ---------------------------------------------------------------------------
# Public runner API
# ---------------------------------------------------------------------------

def run_eval(
    fixtures_dir: str | Path,
    strategy: str = "text_extractor",
) -> dict[str, Any]:
    """Run eval across all fixtures for a given strategy.

    For each fixture:
    1. Load input (image/text/url config)
    2. Run the specified strategy to get extraction result
    3. Load expected output from expected/ directory
    4. Score the result
    5. Aggregate scores

    Args:
        fixtures_dir: Path to the fixtures root directory.
        strategy: Strategy key from STRATEGIES registry.

    Returns:
        Summary dict with per-fixture and aggregate scores.
    """
    fixtures_path = Path(fixtures_dir)
    if not fixtures_path.is_dir():
        raise FileNotFoundError(f"Fixtures directory not found: {fixtures_dir}")

    # Determine valid input types for this strategy
    strat_entry = STRATEGIES.get(strategy, {})
    valid_input_types = strat_entry.get("input_types")

    fixtures = _discover_fixtures(fixtures_path, input_types=valid_input_types)
    if not fixtures:
        console.print(f"[yellow]No fixtures found for strategy '{strategy}'[/yellow]")
        return {"strategy": strategy, "fixtures": [], "aggregate": {}}

    console.print(
        f"[bold blue]Running eval:[/bold blue] strategy={strategy}, "
        f"fixtures={len(fixtures)}"
    )

    results: list[dict[str, Any]] = []
    for fixture in fixtures:
        console.print(f"  Evaluating: {fixture['id']}...", end=" ")
        result = _evaluate_fixture(fixture, strategy)
        results.append(result)

        if result["error"]:
            console.print(f"[red]ERROR: {result['error']}[/red]")
        else:
            overall = result["scores"].get("overall_f1", 0)
            color = "green" if overall >= 0.8 else "yellow" if overall >= 0.5 else "red"
            console.print(f"[{color}]F1={overall:.3f}[/{color}]")

    # Aggregate scores
    aggregate = _aggregate_scores(results)

    summary = {
        "strategy": strategy,
        "fixtures": results,
        "aggregate": aggregate,
    }

    # Print summary table
    _print_summary(summary)

    return summary


def run_comparison(
    fixtures_dir: str | Path,
    strategies: list[str],
) -> dict[str, Any]:
    """Run multiple strategies on the same fixtures and compare.

    Args:
        fixtures_dir: Path to the fixtures root directory.
        strategies: List of strategy keys to compare.

    Returns:
        Dict mapping strategy name to its run_eval summary.
    """
    comparison: dict[str, Any] = {}

    for strategy in strategies:
        console.print(f"\n[bold]--- Strategy: {strategy} ---[/bold]")
        try:
            summary = run_eval(fixtures_dir, strategy=strategy)
            comparison[strategy] = summary
        except Exception as e:
            console.print(f"[red]Strategy '{strategy}' failed: {e}[/red]")
            comparison[strategy] = {"error": str(e)}

    # Print comparison table
    if len(comparison) > 1:
        _print_comparison(comparison)

    return comparison


# ---------------------------------------------------------------------------
# Aggregation & display
# ---------------------------------------------------------------------------

def _aggregate_scores(results: list[dict[str, Any]]) -> dict[str, float]:
    """Compute average scores across all fixtures."""
    score_keys = [
        "ingredients_precision",
        "ingredients_recall",
        "amounts_accuracy",
        "steps_completeness",
        "metadata_accuracy",
        "overall_f1",
    ]
    totals: dict[str, list[float]] = {k: [] for k in score_keys}

    for result in results:
        if result.get("error"):
            continue
        scores = result.get("scores", {})
        for key in score_keys:
            if key in scores:
                totals[key].append(scores[key])

    aggregate: dict[str, float] = {}
    for key, values in totals.items():
        if values:
            aggregate[f"{key}_avg"] = sum(values) / len(values)
            aggregate[f"{key}_min"] = min(values)
            aggregate[f"{key}_max"] = max(values)

    aggregate["total_fixtures"] = float(len(results))
    aggregate["fixtures_with_errors"] = float(
        sum(1 for r in results if r.get("error"))
    )

    return aggregate


def _print_summary(summary: dict[str, Any]) -> None:
    """Print a summary table to the console."""
    results = summary.get("fixtures", [])
    aggregate = summary.get("aggregate", {})

    if not results:
        return

    table = Table(title=f"Eval Results: {summary['strategy']}")
    table.add_column("Fixture", style="cyan")
    table.add_column("Precision", justify="right")
    table.add_column("Recall", justify="right")
    table.add_column("Amounts", justify="right")
    table.add_column("Steps", justify="right")
    table.add_column("Metadata", justify="right")
    table.add_column("F1", justify="right", style="bold")
    table.add_column("Time (ms)", justify="right")

    for r in results:
        if r.get("error"):
            table.add_row(r["id"], "[red]ERROR[/red]", "", "", "", "", "", "")
            continue

        scores = r.get("scores", {})
        table.add_row(
            r["id"],
            f"{scores.get('ingredients_precision', 0):.3f}",
            f"{scores.get('ingredients_recall', 0):.3f}",
            f"{scores.get('amounts_accuracy', 0):.3f}",
            f"{scores.get('steps_completeness', 0):.3f}",
            f"{scores.get('metadata_accuracy', 0):.3f}",
            f"{scores.get('overall_f1', 0):.3f}",
            f"{r.get('duration_ms', 0):.0f}",
        )

    # Aggregate row
    if aggregate:
        table.add_section()
        table.add_row(
            "[bold]AVG[/bold]",
            f"{aggregate.get('ingredients_precision_avg', 0):.3f}",
            f"{aggregate.get('ingredients_recall_avg', 0):.3f}",
            f"{aggregate.get('amounts_accuracy_avg', 0):.3f}",
            f"{aggregate.get('steps_completeness_avg', 0):.3f}",
            f"{aggregate.get('metadata_accuracy_avg', 0):.3f}",
            f"{aggregate.get('overall_f1_avg', 0):.3f}",
            "",
        )

    console.print(table)


def _print_comparison(comparison: dict[str, Any]) -> None:
    """Print a comparison table across strategies."""
    table = Table(title="Strategy Comparison")
    table.add_column("Strategy", style="cyan")
    table.add_column("Avg F1", justify="right", style="bold")
    table.add_column("Avg Precision", justify="right")
    table.add_column("Avg Recall", justify="right")
    table.add_column("Avg Amounts", justify="right")
    table.add_column("Avg Steps", justify="right")
    table.add_column("Avg Metadata", justify="right")
    table.add_column("Errors", justify="right")

    for strategy, summary in comparison.items():
        if "error" in summary:
            table.add_row(strategy, "[red]FAILED[/red]", "", "", "", "", "", "")
            continue

        agg = summary.get("aggregate", {})
        table.add_row(
            strategy,
            f"{agg.get('overall_f1_avg', 0):.3f}",
            f"{agg.get('ingredients_precision_avg', 0):.3f}",
            f"{agg.get('ingredients_recall_avg', 0):.3f}",
            f"{agg.get('amounts_accuracy_avg', 0):.3f}",
            f"{agg.get('steps_completeness_avg', 0):.3f}",
            f"{agg.get('metadata_accuracy_avg', 0):.3f}",
            f"{int(agg.get('fixtures_with_errors', 0))}",
        )

    console.print("\n")
    console.print(table)
