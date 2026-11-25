#!/usr/bin/env python3
"""Turn a `vision_extraction` eval run into the committed baseline (bugs-imp-pho-7).

AC4 of the vision-eval story wants a first live run captured as the
`field_accuracy` regression reference. The live run costs real money and
happens once, so the numbers must not be hand-transcribed out of a
console table — this script reads the run's JSON straight from
`src.main run --output ...` and rewrites
`baselines/vision_extraction_baseline.json`, plus prints a
PR-pasteable markdown block.

Usage (from `services/eval/`):

    # 1. The one live run (bills 5 gpt-4o-mini vision calls).
    OPENAI_API_KEY=<key> poetry run python -m src.main run \\
        --suite vision_extraction --output results/vision-baseline.json

    # 2. Capture it — writes the baseline file and prints the PR block.
    poetry run python scripts/capture_vision_baseline.py \\
        --results results/vision-baseline.json --markdown

Read-only against the eval suite: it never runs an evaluator and never
touches OpenAI, so re-running it is free.

Exit codes: 0 captured, 2 no `vision_extraction` suite in the results
file (or every case skipped — nothing to baseline), 1 unreadable input.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = EVAL_DIR / "baselines" / "vision_extraction_baseline.json"
DEFAULT_RESULTS_GLOB = "eval_*.json"
SUITE = "vision_extraction"

# Suite-level metric keys carried into the baseline, in report order.
# Anything the run didn't emit lands as null rather than being silently
# dropped, so a missing metric reads as "not measured", not "measured as
# zero".
#
# `unit_enum_compliance` is deliberately absent: the evaluator emits it
# as a *dict* (compliance + non-canonical token breakdown), and
# runner._calculate_metrics_summary only averages int/float values, so
# `unit_enum_compliance_avg` never exists. Its scalar is pinned per-case
# instead (see PER_CASE_METRICS).
BASELINE_METRICS = [
    "recipe_count_accuracy_avg",
    "multi_recipe_count_accuracy_avg",
    "field_accuracy_avg",
    "ingredient_count_accuracy_avg",
    "instruction_similarity_avg",
    "timer_extraction_f1_avg",
]

# Per-case fields worth pinning: the count pair explains any gate
# failure at a glance, field_accuracy is the regression reference.
PER_CASE_METRICS = [
    "recipe_count_accuracy",
    "expected_recipe_count",
    "actual_recipe_count",
    "field_accuracy",
]

# Per-case metrics reported as a dict; the scalar named here is lifted
# out so the baseline stays a flat, diffable set of numbers.
PER_CASE_NESTED_METRICS = {"unit_enum_compliance": "compliance"}

HARD_GATED = {"recipe_count_accuracy_avg", "multi_recipe_count_accuracy_avg"}


def find_latest_results(results_dir: Path) -> Path | None:
    """Newest `eval_*.json` in the results dir, or None."""
    candidates = sorted(results_dir.glob(DEFAULT_RESULTS_GLOB), reverse=True)
    return candidates[0] if candidates else None


def current_commit() -> str | None:
    """Short SHA of HEAD, or None outside a git checkout."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=EVAL_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def build_baseline(
    results: dict,
    *,
    generated_at: str,
    commit: str | None,
    results_file: str | None,
    threshold: float = 0.8,
    previous: dict | None = None,
) -> dict:
    """Project an `EvalResults.to_dict()` payload onto the baseline shape.

    Raises:
        LookupError: the payload has no `vision_extraction` suite, or
            every one of its cases was skipped (a mock/cold-cache run —
            there is nothing to baseline).
    """
    suite = (results.get("suite_results") or {}).get(SUITE)
    if suite is None:
        raise LookupError(
            f"no '{SUITE}' suite in results "
            f"(found: {sorted((results.get('suite_results') or {}))})"
        )

    case_results = suite.get("results") or []
    graded = [r for r in case_results if not r.get("skipped")]
    if not graded:
        raise LookupError(
            f"every '{SUITE}' case was skipped — that is a mock/cold-cache "
            "run, not a baseline. Re-run with a real OPENAI_API_KEY."
        )

    metrics_summary = suite.get("metrics_summary") or {}
    metrics = {key: metrics_summary.get(key) for key in BASELINE_METRICS}

    per_case = {}
    for result in case_results:
        case = {
            "passed": result.get("passed"),
            "skipped": result.get("skipped", False),
            "cache_hit": result.get("cache_hit", False),
        }
        if result.get("error"):
            case["error"] = result["error"]
        case_metrics = result.get("metrics") or {}
        for key in PER_CASE_METRICS:
            if key in case_metrics:
                case[key] = case_metrics[key]
        for key, scalar in PER_CASE_NESTED_METRICS.items():
            nested = case_metrics.get(key)
            if isinstance(nested, dict) and scalar in nested:
                case[key] = nested[scalar]
        per_case[result["case_id"]] = case

    baseline = json.loads(json.dumps(previous)) if previous else {}
    baseline.setdefault("_comment", "")
    baseline.update(
        _suite=SUITE,
        _generated_at=generated_at,
        _generated_commit=commit,
        _results_file=results_file,
        run={
            "total_cases": suite.get("total_cases"),
            "passed_cases": suite.get("passed_cases"),
            "failed_cases": suite.get("failed_cases"),
            "skipped_cases": suite.get("skipped_cases"),
            "cost_cents": sum(r.get("cost_cents") or 0 for r in case_results),
            "duration_seconds": suite.get("duration_seconds"),
            "passed_threshold": suite.get("passed_threshold"),
        },
        metrics=metrics,
        per_case=per_case,
    )

    thresholds = dict(baseline.get("thresholds") or {})
    thresholds["recipe_count_accuracy"] = threshold
    thresholds["multi_recipe_count_accuracy"] = threshold
    # field_accuracy stays soft, but the captured number is what a future
    # hardening pass reads, so record it here too.
    thresholds["field_accuracy"] = metrics.get("field_accuracy_avg")
    baseline["thresholds"] = thresholds

    return baseline


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown(baseline: dict) -> str:
    """PR-description block: the suite summary + the metric table."""
    run = baseline.get("run") or {}
    metrics = baseline.get("metrics") or {}
    threshold = (baseline.get("thresholds") or {}).get("recipe_count_accuracy")

    lines = [
        "### `vision_extraction` baseline",
        "",
        f"Captured {_fmt(baseline.get('_generated_at'))} "
        f"@ `{_fmt(baseline.get('_generated_commit'))}` — "
        f"{_fmt(run.get('total_cases'))} cases, "
        f"{_fmt(run.get('passed_cases'))} passed / "
        f"{_fmt(run.get('failed_cases'))} failed / "
        f"{_fmt(run.get('skipped_cases'))} skipped, "
        f"cost {_fmt(run.get('cost_cents'))}¢, "
        f"gate {'PASS' if run.get('passed_threshold') else 'FAIL'}.",
        "",
        "| Metric | Value | Gate |",
        "|---|---|---|",
    ]
    for key in BASELINE_METRICS:
        gate = f"hard ≥ {_fmt(threshold)}" if key in HARD_GATED else "reported"
        lines.append(f"| `{key}` | {_fmt(metrics.get(key))} | {gate} |")

    per_case = baseline.get("per_case") or {}
    if per_case:
        lines += [
            "",
            "| Case | Expected N | Actual N | field_accuracy |",
            "|---|---|---|---|",
        ]
        for case_id, case in per_case.items():
            lines.append(
                f"| `{case_id}` | {_fmt(case.get('expected_recipe_count'))} "
                f"| {_fmt(case.get('actual_recipe_count'))} "
                f"| {_fmt(case.get('field_accuracy'))} |"
            )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--results",
        help="Eval results JSON from `src.main run --output`. "
        "Defaults to the newest results/eval_*.json.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_BASELINE),
        help=f"Baseline file to rewrite (default: {DEFAULT_BASELINE}).",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Also print the PR-pasteable markdown block.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the baseline JSON instead of writing it.",
    )
    args = parser.parse_args(argv)

    if args.results:
        results_path = Path(args.results)
    else:
        found = find_latest_results(EVAL_DIR / "results")
        if found is None:
            print(
                "error: no --results given and no results/eval_*.json found",
                file=sys.stderr,
            )
            return 1
        results_path = found

    try:
        payload = json.loads(results_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {results_path}: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    previous = None
    if output_path.exists():
        try:
            previous = json.loads(output_path.read_text())
        except (OSError, json.JSONDecodeError):
            previous = None

    try:
        baseline = build_baseline(
            payload,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            commit=current_commit(),
            results_file=str(results_path),
            previous=previous,
        )
    except LookupError as exc:
        print(f"nothing to capture: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(baseline, indent=2) + "\n"
    if args.dry_run:
        print(rendered, end="")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered)
        print(f"baseline written: {output_path}")

    if args.markdown:
        print()
        print(render_markdown(baseline))

    return 0


if __name__ == "__main__":
    sys.exit(main())
