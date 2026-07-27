"""irrd-3a — the opt-in run that drives both confidence gates.

Two metric modules landed first, each pure arithmetic over samples:

* ``src.metrics.confidence_calibration`` — MAE of
  ``|confidence_score - overall_f1|``, hard-gated at 0.3 (AC8/AC9).
* ``src.metrics.title_extraction`` — ``title_extraction_f1``, soft-gated
  at a 5% relative drop vs the recorded baseline (AC11).

This module is the wiring between them and a real fixture run: it turns
``fixture_runner.run_eval(..., include_payloads=True)`` output into the
samples each metric wants, applies both gates, and renders one report
carrying both pass/fail blocks.

Producing the samples costs an ``OPENAI_API_KEY`` and ~10 minutes, so
the entry point is explicitly invoked (``npx nx run eval:confidence-gate``)
and is never part of the fast CI path. Everything in this module except
:func:`run_confidence_gates` is a pure function over already-collected
results, so the wiring itself is unit-tested offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.metrics.confidence_calibration import (
    CALIBRATION_MAE_THRESHOLD,
    check_calibration_gate,
    compute_confidence_calibration,
    dominant_signal,
    format_calibration_summary,
)
from src.metrics.title_extraction import (
    TITLE_REGRESSION_MAX_RELATIVE_DROP,
    check_title_regression_gate,
    compute_title_extraction_f1,
    format_title_regression_summary,
)

# services/eval/baselines/ — resolved from this file so the command works
# from any cwd.
BASELINES_DIR = Path(__file__).resolve().parents[1] / "baselines"
CALIBRATION_BASELINE_PATH = BASELINES_DIR / "confidence_calibration_baseline.json"
EXTRACTION_BASELINE_PATH = BASELINES_DIR / "extraction_baseline.json"

# Aggregate keys copied into the extraction baseline for diagnostic
# context (see fixture_runner._aggregate_scores).
_AGGREGATE_KEYS: tuple[str, ...] = (
    "ingredients_precision_avg",
    "ingredients_recall_avg",
    "amounts_accuracy_avg",
    "steps_completeness_avg",
    "metadata_accuracy_avg",
    "overall_f1_avg",
    "total_fixtures",
    "fixtures_with_errors",
)


# ---------------------------------------------------------------------------
# Baseline I/O
# ---------------------------------------------------------------------------

def load_baseline(path: str | Path) -> dict[str, Any] | None:
    """Load a baseline JSON file, or ``None`` when it is absent/unreadable.

    A missing baseline is not an error: the title gate treats it as
    "nothing to regress against", and the calibration gate decides on its
    own threshold either way.
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        loaded = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


# ---------------------------------------------------------------------------
# Fixture results -> metric samples
# ---------------------------------------------------------------------------

def _structural_signals(recipe: Any) -> dict[str, float]:
    """Signals the heuristic weighed, read from the production module.

    Imported lazily so importing this module (and unit-testing the
    wiring) does not pull in the extractor package.
    """
    from utils.services.recipe_extractors.confidence_heuristic import structural_signals

    return structural_signals(recipe)


def _usable(result: Any) -> bool:
    """A fixture that errored produced no extraction to judge."""
    return (
        isinstance(result, dict)
        and not result.get("error")
        and isinstance(result.get("extracted"), dict)
    )


def build_calibration_samples(
    fixture_results: list[dict[str, Any]],
    with_signals: bool = True,
) -> list[dict[str, Any]]:
    """Pair each fixture's emitted confidence with the F1 it actually scored.

    ``with_signals`` computes the heuristic's structural signals from the
    extracted recipe so the calibration result can report which factor
    correlates best with truth — the evidence AC9's retune needs. Turn it
    off to keep the wiring free of extractor imports.
    """
    samples: list[dict[str, Any]] = []
    for result in fixture_results:
        if not _usable(result):
            continue
        extracted = result["extracted"]
        sample: dict[str, Any] = {
            "fixture_id": result.get("id", "unknown"),
            "confidence": extracted.get("confidence_score"),
            "ground_truth_f1": (result.get("scores") or {}).get("overall_f1"),
            "source": extracted.get("confidence_source") or "unknown",
        }
        if with_signals:
            sample["signals"] = _structural_signals(extracted)
        samples.append(sample)
    return samples


def build_title_pairs(
    fixture_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair each fixture's extracted recipe with its ground-truth recipe.

    ``run_eval`` already unwraps the ``{"recipes": [...]}`` envelope (see
    ``fixture_runner.unwrap_expected_recipe``), so ``expected`` here is
    always a bare recipe dict.
    """
    return [
        {
            "fixture_id": result.get("id", "unknown"),
            "extracted": result["extracted"],
            "expected": result.get("expected"),
        }
        for result in fixture_results
        if _usable(result)
    ]


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def evaluate_gates(
    fixture_results: list[dict[str, Any]],
    calibration_baseline: dict[str, Any] | None = None,
    extraction_baseline: dict[str, Any] | None = None,
    aggregate: dict[str, Any] | None = None,
    strategy: str = "text_extractor",
    with_signals: bool = True,
) -> dict[str, Any]:
    """Run both gates over one fixture run and combine the verdicts.

    The run passes only when *both* gates pass. An empty or fully-errored
    run fails: both metrics report ``None`` on no samples and both gates
    refuse to pass on an unknown value.
    """
    calibration_result = compute_confidence_calibration(
        build_calibration_samples(fixture_results, with_signals=with_signals)
    )
    calibration_gate = check_calibration_gate(
        calibration_result, baseline=calibration_baseline
    )

    title_result = compute_title_extraction_f1(build_title_pairs(fixture_results))
    title_gate = check_title_regression_gate(title_result, baseline=extraction_baseline)

    errored = [
        r.get("id", "unknown")
        for r in fixture_results
        if isinstance(r, dict) and r.get("error")
    ]

    return {
        "strategy": strategy,
        "fixture_count": len(fixture_results),
        "errored_fixtures": errored,
        "aggregate": dict(aggregate or {}),
        "calibration": {"result": calibration_result, "gate": calibration_gate},
        "title": {"result": title_result, "gate": title_gate},
        "passed": bool(calibration_gate.get("passed") and title_gate.get("passed")),
    }


def format_gate_report(report: dict[str, Any]) -> str:
    """Render both gate summaries plus a combined verdict.

    Everything needed to diagnose a failure — metric value, baseline,
    threshold, worst fixtures — comes from the two per-gate summaries;
    this adds the run-level context (strategy, fixtures, extraction
    errors) and the single line CI reads.
    """
    calibration = report.get("calibration") or {}
    title = report.get("title") or {}
    errored = report.get("errored_fixtures") or []

    lines = [
        "",
        f"Run: strategy={report.get('strategy', 'unknown')} "
        f"fixtures={report.get('fixture_count', 0)}",
    ]
    if errored:
        lines.append(
            f"Extraction errors ({len(errored)}): {', '.join(errored)} "
            "— excluded from both metrics"
        )
    lines.append("")
    lines.append(
        format_calibration_summary(
            calibration.get("result") or {}, calibration.get("gate") or {}
        )
    )
    lines.append("")
    lines.append(
        format_title_regression_summary(title.get("result") or {}, title.get("gate") or {})
    )
    lines.append("")
    lines.append(
        f"OVERALL: {'PASSED' if report.get('passed') else 'FAILED'} "
        f"(calibration={'pass' if (calibration.get('gate') or {}).get('passed') else 'FAIL'}, "
        f"title={'pass' if (title.get('gate') or {}).get('passed') else 'FAIL'})"
    )

    if not (calibration.get("gate") or {}).get("passed"):
        winner = dominant_signal(calibration.get("result") or {})
        if winner:
            lines.append(
                f"  AC9 next step: shift heuristic weight toward '{winner}' in "
                "libraries/utils/utils/services/recipe_extractors/confidence_heuristic.py"
            )
    if not (title.get("gate") or {}).get("passed"):
        lines.append(
            "  AC11 next step: retune the confidence-emitting prompts "
            "(EXTRACTOR_EMIT_CONFIDENCE) before this story completes"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Baseline refresh
# ---------------------------------------------------------------------------

def build_calibration_baseline(
    report: dict[str, Any],
    existing: dict[str, Any] | None = None,
    generated_at: str | None = None,
    generated_commit: str | None = None,
) -> dict[str, Any]:
    """Merge a run's calibration numbers into the checked-in baseline.

    Merge, not replace: every ``_comment`` in the file explains how the
    number was produced and what re-generating it costs, which is the
    part a future reader needs most.
    """
    from utils.services.recipe_extractors import confidence_heuristic as heuristic

    payload = json.loads(json.dumps(existing)) if existing else {}
    result = (report.get("calibration") or {}).get("result") or {}

    payload["_generated_at"] = generated_at
    payload["_generated_commit"] = generated_commit

    section = dict(payload.get("confidence_calibration") or {})
    section.update({
        "mae": result.get("mae"),
        "sample_count": result.get("sample_count", 0),
        "bias": result.get("bias"),
        "mean_confidence": result.get("mean_confidence"),
        "mean_ground_truth_f1": result.get("mean_ground_truth_f1"),
        "by_source": {
            source: {
                "mae": stats.get("mae"),
                "sample_count": stats.get("sample_count", 0),
            }
            for source, stats in (result.get("by_source") or {}).items()
        },
        "signal_correlations": dict(result.get("signal_correlations") or {}),
    })
    payload["confidence_calibration"] = section

    weights = dict(payload.get("heuristic_weights") or {})
    weights.update({
        "ingredients": heuristic._W_INGREDIENTS,
        "title": heuristic._W_TITLE,
        "steps": heuristic._W_STEPS,
    })
    payload["heuristic_weights"] = weights

    thresholds = dict(payload.get("thresholds") or {})
    thresholds["confidence_calibration_mae_max"] = CALIBRATION_MAE_THRESHOLD
    payload["thresholds"] = thresholds

    return payload


def build_extraction_baseline(
    report: dict[str, Any],
    existing: dict[str, Any] | None = None,
    generated_at: str | None = None,
    generated_commit: str | None = None,
) -> dict[str, Any]:
    """Merge a run's title + aggregate numbers into the checked-in baseline."""
    payload = json.loads(json.dumps(existing)) if existing else {}
    result = (report.get("title") or {}).get("result") or {}
    aggregate = report.get("aggregate") or {}

    payload["_generated_at"] = generated_at
    payload["_generated_commit"] = generated_commit
    payload["_strategy"] = report.get("strategy", payload.get("_strategy"))

    section = dict(payload.get("title_extraction") or {})
    section.update({
        "title_extraction_f1": result.get("title_extraction_f1"),
        "precision": result.get("precision"),
        "recall": result.get("recall"),
        "exact_match_rate": result.get("exact_match_rate"),
        "sample_count": result.get("sample_count", 0),
    })
    payload["title_extraction"] = section

    scores = dict(payload.get("extraction_scores") or {})
    for key in _AGGREGATE_KEYS:
        if key in aggregate:
            scores[key] = aggregate[key]
    payload["extraction_scores"] = scores

    thresholds = dict(payload.get("thresholds") or {})
    thresholds["title_extraction_f1_max_relative_drop"] = (
        TITLE_REGRESSION_MAX_RELATIVE_DROP
    )
    payload["thresholds"] = thresholds

    return payload


def write_baselines(
    report: dict[str, Any],
    generated_at: str | None = None,
    generated_commit: str | None = None,
    calibration_path: str | Path = CALIBRATION_BASELINE_PATH,
    extraction_path: str | Path = EXTRACTION_BASELINE_PATH,
) -> list[Path]:
    """Rewrite both baseline files from ``report``. Returns paths written."""
    written: list[Path] = []
    for path, builder in (
        (Path(calibration_path), build_calibration_baseline),
        (Path(extraction_path), build_extraction_baseline),
    ):
        payload = builder(
            report,
            existing=load_baseline(path),
            generated_at=generated_at,
            generated_commit=generated_commit,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# The opt-in run
# ---------------------------------------------------------------------------

def run_confidence_gates(
    fixtures_dir: str | Path,
    strategy: str = "text_extractor",
    calibration_baseline_path: str | Path = CALIBRATION_BASELINE_PATH,
    extraction_baseline_path: str | Path = EXTRACTION_BASELINE_PATH,
) -> dict[str, Any]:
    """Run the fixtures for real, then apply both gates.

    This is the expensive half: it calls the production extractors, which
    means ``OPENAI_API_KEY`` and roughly ten minutes for the checked-in
    fixture set. Returns the report dict; rendering and exit codes are
    the caller's job.
    """
    from src.fixture_runner import run_eval

    summary = run_eval(fixtures_dir, strategy=strategy, include_payloads=True)
    return evaluate_gates(
        summary.get("fixtures") or [],
        calibration_baseline=load_baseline(calibration_baseline_path),
        extraction_baseline=load_baseline(extraction_baseline_path),
        aggregate=summary.get("aggregate") or {},
        strategy=strategy,
    )
