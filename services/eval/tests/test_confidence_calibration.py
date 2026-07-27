"""irrd-3a — unit tests for the confidence-calibration metric + gate.

Deterministic only: pure arithmetic over hand-built samples, no network
and no OPENAI_API_KEY. The expensive real-LLM run that *produces*
samples is opt-in and lives outside pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.metrics.confidence_calibration import (
    CALIBRATION_MAE_THRESHOLD,
    SIGNAL_NAMES,
    CalibrationSample,
    check_calibration_gate,
    compute_confidence_calibration,
    dominant_signal,
    format_calibration_summary,
)

# -------------------------------------------------------------------
# MAE math
# -------------------------------------------------------------------


def test_perfect_calibration_is_zero_mae():
    samples = [
        CalibrationSample("a", confidence=0.9, ground_truth_f1=0.9),
        CalibrationSample("b", confidence=0.5, ground_truth_f1=0.5),
    ]
    out = compute_confidence_calibration(samples)
    assert out["mae"] == 0.0
    assert out["sample_count"] == 2


def test_mae_is_mean_absolute_error():
    # errors: |0.9-0.5| = 0.4, |0.2-0.4| = 0.2  -> mean 0.3
    samples = [
        CalibrationSample("a", confidence=0.9, ground_truth_f1=0.5),
        CalibrationSample("b", confidence=0.2, ground_truth_f1=0.4),
    ]
    out = compute_confidence_calibration(samples)
    assert out["mae"] == 0.30000000000000004 or abs(out["mae"] - 0.3) < 1e-9


def test_bias_is_signed_and_flags_overconfidence():
    samples = [
        CalibrationSample("a", confidence=0.9, ground_truth_f1=0.5),
        CalibrationSample("b", confidence=0.8, ground_truth_f1=0.6),
    ]
    out = compute_confidence_calibration(samples)
    assert out["bias"] > 0  # overconfident
    assert abs(out["bias"] - 0.3) < 1e-9


def test_bias_negative_when_underconfident():
    samples = [CalibrationSample("a", confidence=0.3, ground_truth_f1=0.9)]
    out = compute_confidence_calibration(samples)
    assert out["bias"] < 0


def test_empty_input_yields_none_not_zero():
    out = compute_confidence_calibration([])
    assert out["mae"] is None
    assert out["sample_count"] == 0


# -------------------------------------------------------------------
# Input coercion / robustness
# -------------------------------------------------------------------


def test_accepts_dicts_from_runner():
    out = compute_confidence_calibration([
        {"fixture_id": "x", "confidence": 0.7, "ground_truth_f1": 0.7},
    ])
    assert out["mae"] == 0.0
    assert out["per_fixture"][0]["fixture_id"] == "x"


def test_accepts_runner_alias_keys():
    # The fixture runner emits `id` / `overall_f1` / `confidence_source`.
    out = compute_confidence_calibration([
        {
            "id": "potato_quiche",
            "confidence_score": 0.8,
            "overall_f1": 0.6,
            "confidence_source": "model",
        },
    ])
    assert abs(out["mae"] - 0.2) < 1e-9
    assert out["per_fixture"][0]["fixture_id"] == "potato_quiche"
    assert out["by_source"]["model"]["sample_count"] == 1


def test_accepts_bare_pairs():
    out = compute_confidence_calibration([(0.5, 0.5), (0.4, 0.2)])
    assert abs(out["mae"] - 0.1) < 1e-9


def test_non_finite_samples_are_skipped_not_zeroed():
    samples = [
        CalibrationSample("good", confidence=0.5, ground_truth_f1=0.5),
        CalibrationSample("nan", confidence=float("nan"), ground_truth_f1=0.5),
        CalibrationSample("inf", confidence=float("inf"), ground_truth_f1=0.5),
        CalibrationSample("none", confidence=None, ground_truth_f1=0.5),
    ]
    out = compute_confidence_calibration(samples)
    assert out["sample_count"] == 1
    assert out["skipped_count"] == 3
    assert out["mae"] == 0.0


def test_bool_confidence_is_rejected():
    out = compute_confidence_calibration([
        {"fixture_id": "b", "confidence": True, "ground_truth_f1": 0.5},
    ])
    assert out["sample_count"] == 0
    assert out["skipped_count"] == 1


def test_garbage_entries_are_skipped():
    out = compute_confidence_calibration(["nope", None, 42])
    assert out["sample_count"] == 0
    assert out["skipped_count"] == 3


# -------------------------------------------------------------------
# Per-source split + worst offenders
# -------------------------------------------------------------------


def test_by_source_splits_model_and_heuristic():
    samples = [
        CalibrationSample("a", 0.9, 0.9, source="model"),
        CalibrationSample("b", 0.9, 0.3, source="heuristic"),
    ]
    out = compute_confidence_calibration(samples)
    assert out["by_source"]["model"]["mae"] == 0.0
    assert abs(out["by_source"]["heuristic"]["mae"] - 0.6) < 1e-9


def test_worst_offenders_sorted_by_abs_error_and_capped():
    samples = [
        CalibrationSample(f"f{i}", confidence=0.9, ground_truth_f1=0.9 - i * 0.1)
        for i in range(5)
    ]
    out = compute_confidence_calibration(samples)
    worst = out["worst_offenders"]
    assert len(worst) == 3
    assert worst[0]["fixture_id"] == "f4"
    assert worst[0]["abs_error"] >= worst[1]["abs_error"]


# -------------------------------------------------------------------
# Signal correlations (AC9 retune evidence)
# -------------------------------------------------------------------


def test_correlation_identifies_dominant_signal():
    # `steps` tracks ground-truth F1 exactly; `ingredients` runs inverse.
    samples = [
        CalibrationSample(
            f"f{i}",
            confidence=0.5,
            ground_truth_f1=f1,
            signals={"steps": f1, "ingredients": 1.0 - f1, "title": 1.0},
        )
        for i, f1 in enumerate([0.2, 0.4, 0.6, 0.8])
    ]
    out = compute_confidence_calibration(samples)
    assert abs(out["signal_correlations"]["steps"] - 1.0) < 1e-9
    assert abs(out["signal_correlations"]["ingredients"] + 1.0) < 1e-9
    # Constant signal -> undefined correlation, not 0.0.
    assert out["signal_correlations"]["title"] is None
    assert dominant_signal(out) in {"steps", "ingredients"}


def test_correlation_none_without_signals():
    out = compute_confidence_calibration([
        CalibrationSample("a", 0.5, 0.5),
        CalibrationSample("b", 0.6, 0.6),
    ])
    assert all(v is None for v in out["signal_correlations"].values())
    assert dominant_signal(out) is None


# -------------------------------------------------------------------
# Gate
# -------------------------------------------------------------------


def test_gate_passes_at_or_below_threshold():
    out = compute_confidence_calibration([(0.6, 0.3)])  # MAE exactly 0.3
    gate = check_calibration_gate(out)
    assert gate["passed"] is True
    assert gate["threshold"] == CALIBRATION_MAE_THRESHOLD


def test_gate_fails_above_threshold():
    out = compute_confidence_calibration([(0.9, 0.2)])  # MAE 0.7
    gate = check_calibration_gate(out)
    assert gate["passed"] is False
    assert "retune" in gate["reason"]


def test_gate_fails_closed_on_empty_run():
    gate = check_calibration_gate(compute_confidence_calibration([]))
    assert gate["passed"] is False
    assert gate["value"] is None
    assert "no samples" in gate["reason"]


def test_gate_reports_delta_vs_baseline():
    out = compute_confidence_calibration([(0.5, 0.3)])  # MAE 0.2
    gate = check_calibration_gate(out, baseline={"mae": 0.15})
    assert gate["baseline"] == 0.15
    assert abs(gate["delta_vs_baseline"] - 0.05) < 1e-9


def test_gate_reads_nested_baseline_shape():
    out = compute_confidence_calibration([(0.5, 0.3)])
    gate = check_calibration_gate(
        out, baseline={"confidence_calibration": {"mae": 0.1}}
    )
    assert gate["baseline"] == 0.1


def test_gate_tolerates_null_baseline_placeholder():
    out = compute_confidence_calibration([(0.5, 0.3)])
    gate = check_calibration_gate(out, baseline={"confidence_calibration": {"mae": None}})
    assert gate["baseline"] is None
    assert gate["delta_vs_baseline"] is None
    assert gate["passed"] is True


def test_custom_threshold_respected():
    out = compute_confidence_calibration([(0.5, 0.3)])  # MAE 0.2
    assert check_calibration_gate(out, threshold=0.1)["passed"] is False
    assert check_calibration_gate(out, threshold=0.25)["passed"] is True


# -------------------------------------------------------------------
# Summary output (diagnosable from run output alone)
# -------------------------------------------------------------------


def test_summary_contains_metric_baseline_and_threshold():
    out = compute_confidence_calibration([
        CalibrationSample("a", 0.9, 0.2, source="heuristic"),
    ])
    gate = check_calibration_gate(out, baseline={"mae": 0.1})
    text = format_calibration_summary(out, gate)
    assert "FAILED" in text
    assert "MAE" in text
    assert "threshold" in text
    assert "baseline MAE" in text
    assert "0.1000" in text  # baseline value rendered
    assert "a" in text  # worst-offender fixture id


def test_summary_renders_on_empty_run_without_crashing():
    out = compute_confidence_calibration([])
    gate = check_calibration_gate(out)
    text = format_calibration_summary(out, gate)
    assert "FAILED" in text
    assert "n/a" in text


def test_summary_reports_dominant_signal_when_available():
    samples = [
        CalibrationSample(
            f"f{i}", 0.5, f1, signals={"steps": f1, "ingredients": 0.5, "title": 1.0}
        )
        for i, f1 in enumerate([0.2, 0.5, 0.9])
    ]
    out = compute_confidence_calibration(samples)
    gate = check_calibration_gate(out)
    text = format_calibration_summary(out, gate)
    assert "strongest signal: steps" in text


# -------------------------------------------------------------------
# Baseline file — shape + drift guards
# -------------------------------------------------------------------

BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "baselines"
    / "confidence_calibration_baseline.json"
)


def _load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_baseline_file_exists_and_parses():
    baseline = _load_baseline()
    assert "confidence_calibration" in baseline
    assert "thresholds" in baseline


def test_baseline_is_consumable_by_the_gate():
    # The checked-in placeholder must not crash the gate wiring.
    out = compute_confidence_calibration([(0.5, 0.4)])
    gate = check_calibration_gate(out, baseline=_load_baseline())
    assert gate["passed"] is True
    assert gate["baseline"] is None  # placeholder still null


def test_baseline_threshold_matches_module_constant():
    threshold = _load_baseline()["thresholds"]["confidence_calibration_mae_max"]
    assert threshold == CALIBRATION_MAE_THRESHOLD


def test_baseline_weights_match_live_heuristic():
    """AC9 retunes weights; the baseline must be updated in the same commit."""
    from utils.services.recipe_extractors import confidence_heuristic as ch

    weights = _load_baseline()["heuristic_weights"]
    assert weights["ingredients"] == ch._W_INGREDIENTS
    assert weights["title"] == ch._W_TITLE
    assert weights["steps"] == ch._W_STEPS


def test_live_heuristic_weights_sum_to_one():
    from utils.services.recipe_extractors import confidence_heuristic as ch

    total = ch._W_INGREDIENTS + ch._W_TITLE + ch._W_STEPS
    assert abs(total - 1.0) < 1e-9


def test_baseline_signal_keys_match_module():
    signals = _load_baseline()["confidence_calibration"]["signal_correlations"]
    assert set(signals) == set(SIGNAL_NAMES)
