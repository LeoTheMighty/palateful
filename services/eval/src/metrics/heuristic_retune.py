"""irrd-3a AC9 — turn "retune the heuristic weights" into a computed answer.

The calibration gate (``src.metrics.confidence_calibration``) says *that*
MAE is too high and *which* structural signal correlates best with
ground-truth F1. AC9 then asks for weights "shifted proportionally toward
whichever factor correlates most" until MAE <= 0.3. That last step was
prose: an operator reading the report and hand-editing three constants in
``confidence_heuristic.py``, then paying another ten-minute LLM run to
find out whether the edit worked.

This module closes that loop offline. Because the heuristic is a pure
function of three already-recorded signals, a candidate weight vector's
MAE can be *replayed* against the samples from a single expensive run —
no re-extraction, no second API bill. So we search the shift fractions,
report the smallest one that clears the threshold, and print the exact
constant edit.

Two honesties the search preserves:

* **Model-sourced samples are immovable.** When the LLM self-assessed,
  the heuristic never fired and no weight vector changes that sample's
  error. They stay in the MAE (the gate measures shipped confidence, not
  heuristic confidence) but they cap how far a retune can get.
* **The dominant signal is preferred, not assumed.** AC9's rule is a good
  prior, and it is tried first — but the correlation can be negative or
  effectively tied, in which case shifting toward it makes calibration
  worse. Every candidate is scored empirically and the winner is whatever
  actually lowers MAE, with the dominant signal breaking ties.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

from src.metrics.confidence_calibration import (
    CALIBRATION_MAE_THRESHOLD,
    SIGNAL_NAMES,
    CalibrationSample,
    coerce_samples,
    compute_confidence_calibration,
    dominant_signal,
)

# Shift fractions tried, smallest first: a retune should disturb the
# shipped weights as little as the threshold allows. Each value is the
# fraction of the *other* signals' weight reallocated to the target.
DEFAULT_SHIFT_STEPS: tuple[float, ...] = (
    0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.65, 0.80, 1.00,
)

# Proposed weights are rounded to this many decimals — they land as
# hand-readable constants in confidence_heuristic.py, not as float noise.
_WEIGHT_DECIMALS = 3

# Only these samples respond to a weight change.
_HEURISTIC_SOURCE = "heuristic"


def default_weights() -> dict[str, float]:
    """The weights currently shipping, read from the production module.

    Imported lazily so this module stays importable (and unit-testable)
    without the extractor package on the path.
    """
    from utils.services.recipe_extractors import confidence_heuristic as heuristic

    return {
        "ingredients": heuristic._W_INGREDIENTS,
        "title": heuristic._W_TITLE,
        "steps": heuristic._W_STEPS,
    }


def shift_weights(
    weights: dict[str, float],
    toward: str,
    fraction: float,
) -> dict[str, float]:
    """Move ``fraction`` of the other signals' weight onto ``toward``.

    "Proportionally" per AC9: each non-target weight is scaled by
    ``1 - fraction``, so a signal already carrying more weight gives up
    more. The total is preserved exactly — the rounding remainder is
    absorbed by the target, which keeps ``sum == 1.0`` so the heuristic's
    output stays inside [0, 1] without relying on its clamp.

    ``fraction`` is clamped to [0, 1]; an unknown ``toward`` returns the
    weights unchanged.
    """
    if toward not in weights:
        return dict(weights)
    fraction = max(0.0, min(1.0, fraction))

    total = sum(weights.values())
    proposed = {
        name: round(value * (1.0 - fraction), _WEIGHT_DECIMALS)
        for name, value in weights.items()
        if name != toward
    }
    # Target takes whatever is left of the original total, so rounding
    # never leaks weight in or out.
    proposed[toward] = round(total - sum(proposed.values()), _WEIGHT_DECIMALS)
    return {name: proposed[name] for name in weights}


def _heuristic_confidence(signals: dict[str, float], weights: dict[str, float]) -> float:
    """Replay ``compute_heuristic_confidence`` for a candidate weight vector."""
    score = sum(weights.get(name, 0.0) * signals.get(name, 0.0) for name in weights)
    return max(0.0, min(1.0, score))


def _replayable(sample: CalibrationSample) -> bool:
    """Whether a weight change can move this sample's confidence.

    Requires a heuristic-sourced score and a complete signal breakdown —
    a partial breakdown would silently treat missing signals as 0.0 and
    fabricate an error the real extractor never made.
    """
    return sample.source == _HEURISTIC_SOURCE and all(
        name in sample.signals for name in SIGNAL_NAMES
    )


def simulate_mae(
    samples: Iterable[Any],
    weights: dict[str, float],
) -> dict[str, Any]:
    """MAE the run *would have* reported under ``weights``.

    Heuristic-sourced samples with a complete signal breakdown get their
    confidence recomputed; every other sample keeps the confidence it
    actually shipped. Returns ``mae is None`` on an empty run — same
    fail-closed convention as the gate itself.
    """
    coerced = coerce_samples(samples)
    if not coerced:
        return {
            "mae": None,
            "sample_count": 0,
            "replayed_count": 0,
            "fixed_count": 0,
        }

    errors: list[float] = []
    replayed = 0
    for sample in coerced:
        if _replayable(sample):
            confidence = _heuristic_confidence(sample.signals, weights)
            replayed += 1
        else:
            confidence = sample.confidence
        errors.append(abs(confidence - sample.ground_truth_f1))

    return {
        "mae": sum(errors) / len(errors),
        "sample_count": len(coerced),
        "replayed_count": replayed,
        "fixed_count": len(coerced) - replayed,
    }


def _candidate_targets(result: dict[str, Any]) -> list[str]:
    """Signals to try, dominant first (AC9's prior), then the rest."""
    winner = dominant_signal(result)
    ordered = [winner] if winner in SIGNAL_NAMES else []
    ordered.extend(name for name in SIGNAL_NAMES if name not in ordered)
    return ordered


def propose_retuned_weights(
    samples: Iterable[Any],
    current_weights: dict[str, float] | None = None,
    threshold: float = CALIBRATION_MAE_THRESHOLD,
    shift_steps: Sequence[float] = DEFAULT_SHIFT_STEPS,
    calibration_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Search weight vectors for the smallest shift that clears the gate.

    Args:
        samples: the same samples the calibration metric consumed —
            entries need ``source`` and a ``signals`` breakdown to be
            replayable.
        current_weights: defaults to the shipping weights.
        threshold: the MAE the proposal must reach (AC9's 0.3).
        shift_steps: fractions to try, ascending; the first that clears
            the threshold wins, so a minimal edit is preferred over an
            aggressive one.
        calibration_result: reuse an already-computed calibration result
            instead of recomputing it (they must be over the same samples).

    Returns a dict with ``applicable`` (can weights move this run at
    all?), ``achievable`` (did any candidate reach the threshold?),
    ``weights``, ``shift`` (``{"toward", "fraction"}``), the current and
    projected MAE, and a human ``reason``. ``weights`` always carries a
    usable vector — the best found — even when ``achievable`` is False,
    so an operator can apply it and see how far it got.
    """
    coerced = coerce_samples(samples)
    result = calibration_result or compute_confidence_calibration(coerced)
    weights = dict(current_weights) if current_weights else default_weights()

    baseline = simulate_mae(coerced, weights)
    current_mae = result.get("mae")
    replayable = baseline["replayed_count"]

    proposal: dict[str, Any] = {
        "applicable": False,
        "achievable": False,
        "threshold": threshold,
        "current_weights": dict(weights),
        "weights": dict(weights),
        "shift": None,
        "current_mae": current_mae,
        "projected_mae": current_mae,
        "sample_count": baseline["sample_count"],
        "replayable_count": replayable,
        "immovable_count": baseline["fixed_count"],
        "dominant_signal": dominant_signal(result),
        "candidates": [],
        "reason": "",
    }

    if not coerced:
        proposal["reason"] = "no samples — nothing to retune against"
        return proposal
    if replayable == 0:
        proposal["reason"] = (
            "no heuristic-sourced samples with a signal breakdown — every "
            "score came from the model, so heuristic weights cannot move "
            "this MAE (retune the prompts instead)"
        )
        return proposal
    if isinstance(current_mae, float) and current_mae <= threshold:
        proposal["applicable"] = True
        proposal["achievable"] = True
        proposal["reason"] = (
            f"MAE {current_mae:.4f} already <= {threshold:.2f} — no retune needed"
        )
        return proposal

    proposal["applicable"] = True

    candidates: list[dict[str, Any]] = []
    for rank, target in enumerate(_candidate_targets(result)):
        for fraction in shift_steps:
            candidate_weights = shift_weights(weights, target, fraction)
            simulated = simulate_mae(coerced, candidate_weights)
            if simulated["mae"] is None:
                continue
            candidates.append({
                "toward": target,
                "fraction": fraction,
                "weights": candidate_weights,
                "mae": simulated["mae"],
                "clears": simulated["mae"] <= threshold,
                # Lower rank == closer to AC9's stated rule.
                "_rank": rank,
            })

    proposal["candidates"] = [
        {k: v for k, v in c.items() if not k.startswith("_")} for c in candidates
    ]
    if not candidates:
        proposal["reason"] = "no candidate weight vector could be simulated"
        return proposal

    clearing = [c for c in candidates if c["clears"]]
    if clearing:
        # Minimal disturbance first, then AC9's preferred signal, then MAE.
        best = min(clearing, key=lambda c: (c["fraction"], c["_rank"], c["mae"]))
        proposal["achievable"] = True
        proposal["reason"] = (
            f"shift {best['fraction']:.0%} of the other weights toward "
            f"'{best['toward']}': projected MAE {best['mae']:.4f} "
            f"<= {threshold:.2f}"
        )
    else:
        best = min(candidates, key=lambda c: (c["mae"], c["_rank"], c["fraction"]))
        immovable = proposal["immovable_count"]
        proposal["reason"] = (
            f"no weight vector reaches MAE <= {threshold:.2f}; best is "
            f"{best['mae']:.4f} shifting {best['fraction']:.0%} toward "
            f"'{best['toward']}'"
            + (
                f" ({immovable} of {baseline['sample_count']} samples are "
                "model-sourced and unaffected by weights — retune the prompts "
                "or the signals themselves)"
                if immovable
                else " — the structural signals do not predict F1 well enough"
            )
        )

    proposal["weights"] = best["weights"]
    proposal["shift"] = {"toward": best["toward"], "fraction": best["fraction"]}
    proposal["projected_mae"] = best["mae"]
    return proposal


_CONSTANT_NAMES = {
    "ingredients": "_W_INGREDIENTS",
    "title": "_W_TITLE",
    "steps": "_W_STEPS",
}


def format_retune_proposal(proposal: dict[str, Any]) -> str:
    """Render the proposal as the edit an operator should make.

    Deliberately prints the constant names and the file path: the point
    of AC9's "calibrated weights land in this story's PR" is that the
    run output tells you exactly what to commit.
    """
    if not proposal.get("applicable"):
        return "\n".join([
            "  AC9 retune     : not applicable",
            f"    dominant signal: {proposal.get('dominant_signal')} "
            "(evidence only — no weight change can act on it here)",
            f"    reason: {proposal.get('reason', '')}",
        ])

    if proposal.get("achievable") and proposal.get("shift") is None:
        return "\n".join([
            "  AC9 retune     : none needed",
            f"    reason: {proposal.get('reason', '')}",
        ])

    shift = proposal.get("shift") or {}
    verdict = "PROPOSED" if proposal.get("achievable") else "BEST EFFORT (still fails)"
    lines = [
        f"  AC9 retune     : {verdict}",
        f"    toward       : {shift.get('toward')} "
        f"(dominant signal: {proposal.get('dominant_signal')})",
        f"    shift        : {shift.get('fraction', 0.0):.0%} of the other weights",
        f"    MAE          : {_num(proposal.get('current_mae'))} -> "
        f"{_num(proposal.get('projected_mae'))} "
        f"(threshold {proposal.get('threshold', CALIBRATION_MAE_THRESHOLD):.2f})",
        f"    replayable   : {proposal.get('replayable_count', 0)} of "
        f"{proposal.get('sample_count', 0)} samples "
        f"({proposal.get('immovable_count', 0)} model-sourced, immovable)",
        "    apply to libraries/utils/utils/services/recipe_extractors/"
        "confidence_heuristic.py:",
    ]
    weights = proposal.get("weights") or {}
    current = proposal.get("current_weights") or {}
    for name in SIGNAL_NAMES:
        if name not in weights:
            continue
        was = current.get(name)
        lines.append(
            f"      {_CONSTANT_NAMES.get(name, name)} = {weights[name]}"
            + (f"  # was {was}" if isinstance(was, float) and was != weights[name] else "")
        )
    lines.append(f"    reason: {proposal.get('reason', '')}")
    return "\n".join(lines)


def _num(value: Any, spec: str = ".4f") -> str:
    if isinstance(value, float) and math.isfinite(value):
        return format(value, spec)
    return "n/a"
