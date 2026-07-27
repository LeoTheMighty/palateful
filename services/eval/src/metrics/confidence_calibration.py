"""irrd-3a — calibration of ``confidence_score`` against ground-truth F1.

irrd-3 shipped ``confidence_score`` end-to-end: the extractor either
self-assesses (when ``EXTRACTOR_EMIT_CONFIDENCE`` is on and the model
returns a usable float) or falls back to the structural heuristic in
``utils.services.recipe_extractors.confidence_heuristic``. Neither path
proves the number *means* anything.

This module supplies the proof. For every fixture we already compute an
``overall_f1`` (``src.scoring.score_extraction``) — how good the
extraction actually was. A well-calibrated confidence score tracks that
F1. The headline metric is therefore

    MAE = mean(|confidence - ground_truth_f1|)

with a gate at ``CALIBRATION_MAE_THRESHOLD`` (0.3). Above the threshold
the heuristic weights in ``confidence_heuristic`` get retuned "toward
whichever factor correlates most" — so the result also carries a
per-signal Pearson correlation against ground-truth F1, which is the
evidence that retune needs.

Everything here is pure arithmetic over already-collected samples: no
network, no OpenAI key, no extractor imports. The expensive part (running
the extractors to *produce* the samples) lives in the opt-in runner; this
module is unit-testable offline, per the story's split.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

# The irrd-3 AC9 gate. MAE at or below this is calibrated enough to ship.
CALIBRATION_MAE_THRESHOLD = 0.3

# Signal names mirror the heuristic's weight constants
# (`_W_INGREDIENTS` / `_W_TITLE` / `_W_STEPS`). Keep in sync — a retune
# reads the correlations under these keys to decide where weight goes.
SIGNAL_NAMES: tuple[str, ...] = ("ingredients", "title", "steps")

# How many of the worst-calibrated fixtures to surface in the summary.
_WORST_OFFENDER_COUNT = 3


@dataclass
class CalibrationSample:
    """One fixture's confidence score paired with how it actually scored.

    ``signals`` is the optional structural breakdown the heuristic used
    (keys from :data:`SIGNAL_NAMES`). It is only needed for the retune
    correlations; a sample missing it still contributes to MAE.
    """

    fixture_id: str
    confidence: float
    ground_truth_f1: float
    source: str = "unknown"
    signals: dict[str, float] = field(default_factory=dict)


def _coerce_sample(raw: Any) -> CalibrationSample | None:
    """Accept a CalibrationSample, a dict, or a bare (conf, f1) pair.

    Returns ``None`` for anything whose confidence or F1 isn't a finite
    real number — a fixture that errored out mid-extraction must not be
    silently scored as 0.0 confidence, which would drag MAE toward a
    number nobody can act on.
    """
    if isinstance(raw, CalibrationSample):
        sample = raw
    elif isinstance(raw, dict):
        sample = CalibrationSample(
            fixture_id=str(raw.get("fixture_id") or raw.get("id") or "unknown"),
            confidence=raw.get("confidence", raw.get("confidence_score")),
            ground_truth_f1=raw.get("ground_truth_f1", raw.get("overall_f1")),
            source=str(raw.get("source") or raw.get("confidence_source") or "unknown"),
            signals=raw.get("signals") or {},
        )
    elif isinstance(raw, Sequence) and not isinstance(raw, str | bytes) and len(raw) == 2:
        sample = CalibrationSample(
            fixture_id="unknown",
            confidence=raw[0],
            ground_truth_f1=raw[1],
        )
    else:
        return None

    conf = _finite(sample.confidence)
    truth = _finite(sample.ground_truth_f1)
    if conf is None or truth is None:
        return None

    return CalibrationSample(
        fixture_id=sample.fixture_id,
        confidence=conf,
        ground_truth_f1=truth,
        source=sample.source,
        signals={
            k: v
            for k, v in (sample.signals or {}).items()
            if _finite(v) is not None
        },
    )


def _finite(value: Any) -> float | None:
    """Coerce to float, rejecting bool, NaN, and infinities."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson r, or ``None`` when it is undefined.

    Undefined for fewer than 2 points or when either series is constant
    (zero variance — e.g. every fixture has a title, so the title signal
    is 1.0 everywhere and correlates with nothing).
    """
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    var_x = sum(d * d for d in dx)
    var_y = sum(d * d for d in dy)
    if var_x <= 0 or var_y <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy, strict=True)) / math.sqrt(var_x * var_y)


def compute_confidence_calibration(
    samples: Iterable[Any],
) -> dict[str, Any]:
    """Compute calibration MAE (and retune evidence) over eval fixtures.

    Args:
        samples: Iterable of :class:`CalibrationSample`, equivalent dicts,
            or ``(confidence, ground_truth_f1)`` pairs. Entries with a
            non-finite confidence or F1 are dropped and counted in
            ``skipped_count``.

    Returns:
        ``{"mae", "sample_count", "skipped_count", "bias",
        "mean_confidence", "mean_ground_truth_f1", "per_fixture",
        "worst_offenders", "by_source", "signal_correlations"}``.
        ``mae`` is ``None`` when no sample survived — an empty run is
        "unknown", never "perfect".
    """
    coerced: list[CalibrationSample] = []
    skipped = 0
    for raw in samples:
        sample = _coerce_sample(raw)
        if sample is None:
            skipped += 1
            continue
        coerced.append(sample)

    per_fixture = [
        {
            "fixture_id": s.fixture_id,
            "confidence": s.confidence,
            "ground_truth_f1": s.ground_truth_f1,
            # Signed: positive means the extractor was overconfident.
            "error": s.confidence - s.ground_truth_f1,
            "abs_error": abs(s.confidence - s.ground_truth_f1),
            "source": s.source,
        }
        for s in coerced
    ]

    if not coerced:
        return {
            "mae": None,
            "sample_count": 0,
            "skipped_count": skipped,
            "bias": None,
            "mean_confidence": None,
            "mean_ground_truth_f1": None,
            "per_fixture": [],
            "worst_offenders": [],
            "by_source": {},
            "signal_correlations": dict.fromkeys(SIGNAL_NAMES),
        }

    n = len(coerced)
    mae = sum(row["abs_error"] for row in per_fixture) / n
    bias = sum(row["error"] for row in per_fixture) / n

    by_source: dict[str, dict[str, Any]] = {}
    for source in sorted({s.source for s in coerced}):
        rows = [r for r in per_fixture if r["source"] == source]
        by_source[source] = {
            "mae": sum(r["abs_error"] for r in rows) / len(rows),
            "sample_count": len(rows),
        }

    truths = [s.ground_truth_f1 for s in coerced]
    correlations: dict[str, float | None] = {}
    for name in SIGNAL_NAMES:
        paired = [
            (s.signals[name], s.ground_truth_f1)
            for s in coerced
            if name in s.signals
        ]
        if len(paired) < 2:
            correlations[name] = None
            continue
        correlations[name] = _pearson(
            [p[0] for p in paired], [p[1] for p in paired]
        )

    return {
        "mae": mae,
        "sample_count": n,
        "skipped_count": skipped,
        "bias": bias,
        "mean_confidence": sum(s.confidence for s in coerced) / n,
        "mean_ground_truth_f1": sum(truths) / n,
        "per_fixture": per_fixture,
        "worst_offenders": sorted(
            per_fixture, key=lambda r: r["abs_error"], reverse=True
        )[:_WORST_OFFENDER_COUNT],
        "by_source": by_source,
        "signal_correlations": correlations,
    }


def dominant_signal(result: dict[str, Any]) -> str | None:
    """Which structural signal best predicts ground-truth F1.

    AC9 retunes weights "proportionally toward whichever factor
    correlates most"; this names that factor. Returns ``None`` when no
    signal has a defined correlation — the retune then has no evidence
    to act on and must stay manual.
    """
    correlations = result.get("signal_correlations") or {}
    scored = [
        (name, r) for name, r in correlations.items() if isinstance(r, float)
    ]
    if not scored:
        return None
    return max(scored, key=lambda pair: abs(pair[1]))[0]


def check_calibration_gate(
    result: dict[str, Any],
    threshold: float = CALIBRATION_MAE_THRESHOLD,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the AC9 hard gate: MAE must be ``<= threshold``.

    An empty run (``mae is None``) fails rather than passes — a gate that
    green-lights on zero samples protects nothing.

    ``baseline`` is optional context only; the pass/fail decision is
    against ``threshold``. When supplied, ``delta_vs_baseline`` reports
    the movement (positive = calibration got worse).
    """
    mae = result.get("mae")
    baseline_mae = None
    if isinstance(baseline, dict):
        baseline_mae = _finite(
            (baseline.get("confidence_calibration") or {}).get("mae")
            if "confidence_calibration" in baseline
            else baseline.get("mae")
        )

    if mae is None:
        return {
            "passed": False,
            "metric": "confidence_calibration_mae",
            "value": None,
            "threshold": threshold,
            "baseline": baseline_mae,
            "delta_vs_baseline": None,
            "sample_count": result.get("sample_count", 0),
            "reason": "no samples — calibration unknown, refusing to pass",
        }

    passed = mae <= threshold
    return {
        "passed": passed,
        "metric": "confidence_calibration_mae",
        "value": mae,
        "threshold": threshold,
        "baseline": baseline_mae,
        "delta_vs_baseline": (
            mae - baseline_mae if baseline_mae is not None else None
        ),
        "sample_count": result.get("sample_count", 0),
        "reason": (
            f"MAE {mae:.4f} <= threshold {threshold:.2f}"
            if passed
            else f"MAE {mae:.4f} > threshold {threshold:.2f} — retune "
            f"heuristic weights in confidence_heuristic.py"
        ),
    }


def _fmt(value: Any, spec: str = ".4f") -> str:
    return format(value, spec) if isinstance(value, float) else "n/a"


def format_calibration_summary(
    result: dict[str, Any],
    gate: dict[str, Any],
) -> str:
    """Human-readable pass/fail block for the run output (AC: diagnosable).

    Carries metric value, baseline, and threshold on the headline line so
    a regression is explicable without re-running anything.
    """
    status = "PASSED" if gate.get("passed") else "FAILED"
    lines = [
        "=" * 64,
        f"CONFIDENCE CALIBRATION GATE: {status}",
        "=" * 64,
        f"  MAE            : {_fmt(gate.get('value'))}",
        f"  threshold      : <= {gate.get('threshold'):.2f}",
        f"  baseline MAE   : {_fmt(gate.get('baseline'))}"
        + (
            f"  (delta {gate['delta_vs_baseline']:+.4f})"
            if isinstance(gate.get("delta_vs_baseline"), float)
            else ""
        ),
        f"  fixtures       : {result.get('sample_count', 0)}"
        + (
            f" ({result['skipped_count']} skipped)"
            if result.get("skipped_count")
            else ""
        ),
        f"  mean confidence: {_fmt(result.get('mean_confidence'))}",
        f"  mean truth F1  : {_fmt(result.get('mean_ground_truth_f1'))}",
        f"  bias           : {_fmt(result.get('bias'), '+.4f')}"
        " (positive = overconfident)",
        f"  reason         : {gate.get('reason', '')}",
    ]

    by_source = result.get("by_source") or {}
    if by_source:
        lines.append("  by source      :")
        for source, stats in by_source.items():
            lines.append(
                f"    - {source}: MAE {_fmt(stats.get('mae'))} "
                f"over {stats.get('sample_count', 0)} fixture(s)"
            )

    correlations = result.get("signal_correlations") or {}
    if any(isinstance(r, float) for r in correlations.values()):
        lines.append("  signal r vs F1 :")
        for name in SIGNAL_NAMES:
            lines.append(f"    - {name}: {_fmt(correlations.get(name), '+.4f')}")
        winner = dominant_signal(result)
        if winner:
            lines.append(f"    -> strongest signal: {winner}")

    worst = result.get("worst_offenders") or []
    if worst and not gate.get("passed"):
        lines.append("  worst fixtures :")
        for row in worst:
            lines.append(
                f"    - {row['fixture_id']}: confidence "
                f"{row['confidence']:.3f} vs F1 {row['ground_truth_f1']:.3f} "
                f"(error {row['error']:+.3f})"
            )

    lines.append("=" * 64)
    return "\n".join(lines)
