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
from src.metrics.heuristic_retune import (
    format_retune_proposal,
    propose_retuned_weights,
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

def baseline_emit_confidence(baseline: Any) -> bool | None:
    """The ``EXTRACTOR_EMIT_CONFIDENCE`` state a baseline was captured under.

    ``None`` when the baseline predates this field or never recorded it —
    which is itself worth reporting, because it means the AC11 comparison
    cannot be shown to be a genuine before/after.
    """
    if not isinstance(baseline, dict):
        return None
    value = baseline.get("_emit_confidence")
    return value if isinstance(value, bool) else None


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
# AC11 comparison provenance
# ---------------------------------------------------------------------------

def _flag(state: bool | None) -> str:
    return "unknown" if state is None else f"EXTRACTOR_EMIT_CONFIDENCE={str(state).lower()}"


def classify_ac11_comparison(
    extraction_baseline: dict[str, Any] | None,
    run_emit_confidence: bool | None,
    baseline_missing: bool = False,
) -> dict[str, Any]:
    """Say whether the title gate is actually AC11's before/after comparison.

    AC11 asks one question: did turning the confidence-emitting prompts on
    cost title quality? Answering it needs the baseline captured with
    ``EXTRACTOR_EMIT_CONFIDENCE=false`` and the run with it ``true``. Every
    other pairing still produces a numeric verdict, but that verdict
    answers a *different* question — and a pass would otherwise read as
    "the prompts are fine" when nothing about the prompts was tested.

    Returns a diagnosis, never a gate result: the numeric comparison is
    still valid on its own terms (post-merge the baseline is legitimately
    a confidence-on run, so a same-state pairing is the normal steady
    state), so this classification is reported, not enforced.
    """
    base_state = baseline_emit_confidence(extraction_baseline)
    common: dict[str, Any] = {
        "baseline_emit_confidence": base_state,
        "run_emit_confidence": run_emit_confidence,
    }

    if baseline_missing:
        return {
            **common,
            "kind": "no_baseline",
            "is_before_after": False,
            "note": (
                "no baseline recorded, so nothing was compared — this run "
                f"({_flag(run_emit_confidence)}) establishes it. AC11 wants that "
                "baseline captured with EXTRACTOR_EMIT_CONFIDENCE=false, then a "
                "second run with it true."
            ),
        }

    if base_state is None or run_emit_confidence is None:
        return {
            **common,
            "kind": "unknown",
            "is_before_after": False,
            "note": (
                "cannot confirm this is AC11's before/after: baseline "
                f"{_flag(base_state)}, run {_flag(run_emit_confidence)}. A pass "
                "here does not prove the confidence prompts left titles alone."
            ),
        }

    if base_state is False and run_emit_confidence is True:
        return {
            **common,
            "kind": "before_after",
            "is_before_after": True,
            "note": (
                "valid AC11 before/after — baseline captured with "
                "EXTRACTOR_EMIT_CONFIDENCE=false, this run with it true."
            ),
        }

    if base_state is True and run_emit_confidence is False:
        return {
            **common,
            "kind": "reversed",
            "is_before_after": False,
            "note": (
                "comparison is inverted: the baseline is the confidence-ON run "
                "and this run is confidence-OFF. Re-capture the baseline with "
                "EXTRACTOR_EMIT_CONFIDENCE=false before trusting this as AC11."
            ),
        }

    return {
        **common,
        "kind": "same_state",
        "is_before_after": False,
        "note": (
            f"baseline and run were both captured with {_flag(base_state)} — this "
            "is a drift check, not AC11's before/after. "
            + (
                "A pass does not prove the confidence prompts left titles alone."
                if base_state
                else "The confidence prompts were never exercised."
            )
        ),
    }


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
    current_weights: dict[str, float] | None = None,
    emit_confidence: bool | None = None,
) -> dict[str, Any]:
    """Run both gates over one fixture run and combine the verdicts.

    The run passes only when *both* gates pass. An empty or fully-errored
    run fails: both metrics report ``None`` on no samples and both gates
    refuse to pass on an unknown value.

    When the calibration gate fails, AC9's retune is computed too — the
    samples are already in hand, so the weight search costs nothing on top
    of the run that produced them (see ``src.metrics.heuristic_retune``).
    It needs the structural signals, so it is skipped when
    ``with_signals`` is off.
    """
    calibration_samples = build_calibration_samples(
        fixture_results, with_signals=with_signals
    )
    calibration_result = compute_confidence_calibration(calibration_samples)
    calibration_gate = check_calibration_gate(
        calibration_result, baseline=calibration_baseline
    )
    retune = None
    if with_signals and not calibration_gate.get("passed"):
        retune = propose_retuned_weights(
            calibration_samples,
            current_weights=current_weights,
            calibration_result=calibration_result,
        )

    title_result = compute_title_extraction_f1(build_title_pairs(fixture_results))
    title_gate = check_title_regression_gate(title_result, baseline=extraction_baseline)
    ac11_comparison = classify_ac11_comparison(
        extraction_baseline,
        emit_confidence,
        baseline_missing=bool(title_gate.get("baseline_missing")),
    )

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
        "emit_confidence": emit_confidence,
        "ac11_comparison": ac11_comparison,
        "calibration": {
            "result": calibration_result,
            "gate": calibration_gate,
            "retune": retune,
        },
        "title": {"result": title_result, "gate": title_gate},
        "passed": bool(calibration_gate.get("passed") and title_gate.get("passed")),
    }


def _format_replay_line(replay: dict[str, Any]) -> str:
    """One line saying this report came from a saved run, not a live one.

    Without it a replayed FAILED report is indistinguishable from a fresh
    one, and the operator can't tell whether their weight edit was even
    exercised.
    """
    recomputed = replay.get("recomputed_fixtures") or []
    moved = replay.get("moved_fixtures") or []
    origin = f"REPLAY: saved run {replay.get('source_path', '?')}"
    recorded_at = replay.get("recorded_at")
    if recorded_at:
        origin += f" (recorded {recorded_at})"
    if not replay.get("recompute_heuristic"):
        return origin + " — confidences used exactly as recorded (--as-recorded)"
    return (
        f"{origin} — {len(recomputed)} heuristic confidence(s) recomputed under "
        f"the current weights, {len(moved)} changed; model-sourced scores replayed "
        "verbatim"
    )


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
    replay = report.get("replay")
    if isinstance(replay, dict):
        lines.append(_format_replay_line(replay))
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
    comparison = report.get("ac11_comparison")
    if isinstance(comparison, dict) and comparison.get("note"):
        # Without this, a title gate that compared confidence-on against
        # confidence-on reads exactly like a real AC11 pass.
        prefix = "  AC11 comparison" if comparison.get("is_before_after") else "  WARNING"
        lines.append(f"{prefix}: {comparison['note']}")
    lines.append("")
    lines.append(
        f"OVERALL: {'PASSED' if report.get('passed') else 'FAILED'} "
        f"(calibration={'pass' if (calibration.get('gate') or {}).get('passed') else 'FAIL'}, "
        f"title={'pass' if (title.get('gate') or {}).get('passed') else 'FAIL'})"
    )

    if not (calibration.get("gate") or {}).get("passed"):
        retune = calibration.get("retune")
        if isinstance(retune, dict):
            # The computed answer supersedes the "shift toward X" hint:
            # it names the target, the fraction, the projected MAE, and
            # the literal constants to commit.
            lines.append(format_retune_proposal(retune))
        else:
            winner = dominant_signal(calibration.get("result") or {})
            if winner:
                lines.append(
                    f"  AC9 next step: shift heuristic weight toward '{winner}' in "
                    "libraries/utils/utils/services/recipe_extractors/"
                    "confidence_heuristic.py"
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

def _stamp_emit_confidence(payload: dict[str, Any], report: dict[str, Any]) -> None:
    """Record the flag state a baseline was captured under.

    This is what lets a later run say whether its title comparison is
    AC11's before/after (see :func:`classify_ac11_comparison`). Left
    untouched when the run couldn't determine the state, so an unknown
    never overwrites a known one.
    """
    emit_state = report.get("emit_confidence")
    if isinstance(emit_state, bool):
        payload["_emit_confidence"] = emit_state
        payload["_extractor_flag"] = f"EXTRACTOR_EMIT_CONFIDENCE={str(emit_state).lower()}"


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
    # Explains the by_source mix: with the flag off every sample is
    # heuristic-sourced, which is a different population than a run where
    # the model answered.
    _stamp_emit_confidence(payload, report)

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

    _stamp_emit_confidence(payload, report)

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

def _emit_confidence_state() -> bool | None:
    """Whether ``EXTRACTOR_EMIT_CONFIDENCE`` was on for this run."""
    try:
        from utils.services.recipe_extractors.confidence_prompt import emit_confidence

        return bool(emit_confidence())
    except Exception:
        return None


def run_confidence_gates(
    fixtures_dir: str | Path,
    strategy: str = "text_extractor",
    calibration_baseline_path: str | Path = CALIBRATION_BASELINE_PATH,
    extraction_baseline_path: str | Path = EXTRACTION_BASELINE_PATH,
    save_run_path: str | Path | None = None,
    generated_at: str | None = None,
    generated_commit: str | None = None,
) -> dict[str, Any]:
    """Run the fixtures for real, then apply both gates.

    This is the expensive half: it calls the production extractors, which
    means ``OPENAI_API_KEY`` and roughly ten minutes for the checked-in
    fixture set. Returns the report dict; rendering and exit codes are
    the caller's job.

    ``save_run_path`` persists the run's raw payloads so :func:`replay_gates`
    can re-apply both gates offline after a weight retune — the difference
    between AC9's tuning loop costing one API run and costing one per
    candidate.
    """
    from src.fixture_runner import run_eval

    emit_confidence = _emit_confidence_state()
    summary = run_eval(fixtures_dir, strategy=strategy, include_payloads=True)
    report = evaluate_gates(
        summary.get("fixtures") or [],
        calibration_baseline=load_baseline(calibration_baseline_path),
        extraction_baseline=load_baseline(extraction_baseline_path),
        aggregate=summary.get("aggregate") or {},
        strategy=strategy,
        emit_confidence=emit_confidence,
    )

    if save_run_path is not None:
        from src.run_artifact import save_run_artifact

        saved = save_run_artifact(
            summary,
            save_run_path,
            generated_at=generated_at,
            generated_commit=generated_commit,
            emit_confidence=emit_confidence,
        )
        # Only the path — the payloads themselves stay out of the report
        # so `--output` keeps writing a readable verdict, not a run dump.
        report["saved_run_path"] = str(saved)

    return report


# ---------------------------------------------------------------------------
# The free re-run
# ---------------------------------------------------------------------------

def replay_gates(
    artifact: dict[str, Any],
    calibration_baseline_path: str | Path = CALIBRATION_BASELINE_PATH,
    extraction_baseline_path: str | Path = EXTRACTION_BASELINE_PATH,
    recompute_heuristic: bool = True,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Apply both gates to a run saved by ``--save-run``. No API key, no network.

    This is the loop AC9 actually needs: edit the weights in
    ``confidence_heuristic.py``, replay, read the new MAE. With
    ``recompute_heuristic`` on (the default) every heuristic-sourced
    confidence is recomputed from its saved extraction under the current
    weights — identical to what a fresh run would produce, because the
    heuristic is a pure function of the extracted recipe and extraction
    itself doesn't depend on the weights. Model-sourced scores are
    replayed verbatim; they are exactly the samples a retune cannot move.

    ``recompute_heuristic=False`` reproduces the original run's verdict
    byte-for-byte, which is the right mode for re-reading an old run
    rather than testing a change.
    """
    from src.run_artifact import moved_changes, recompute_heuristic_confidences

    fixture_results = [f for f in (artifact.get("fixtures") or []) if isinstance(f, dict)]
    changes: list[dict[str, Any]] = []
    if recompute_heuristic:
        fixture_results, changes = recompute_heuristic_confidences(fixture_results)

    recorded_emit = artifact.get("emit_confidence")
    report = evaluate_gates(
        fixture_results,
        calibration_baseline=load_baseline(calibration_baseline_path),
        extraction_baseline=load_baseline(extraction_baseline_path),
        aggregate=artifact.get("aggregate") or {},
        strategy=artifact.get("strategy") or "unknown",
        # The flag state that produced these extractions, not the one the
        # replaying shell happens to have set.
        emit_confidence=recorded_emit if isinstance(recorded_emit, bool) else None,
    )
    report["replay"] = {
        "source_path": str(source_path) if source_path is not None else None,
        "recorded_at": artifact.get("_generated_at"),
        "recorded_commit": artifact.get("_generated_commit"),
        "emit_confidence": recorded_emit,
        "recompute_heuristic": recompute_heuristic,
        "recomputed_fixtures": changes,
        "moved_fixtures": moved_changes(changes),
    }
    return report
