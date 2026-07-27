"""irrd-3a AC9 — unit tests for the offline heuristic-weight retune search.

Deterministic only. Every sample here is hand-built, so the whole search
(replay a candidate weight vector against recorded signals, pick the
smallest shift that clears MAE <= 0.3) is exercised without an
OPENAI_API_KEY, network, or the ~10-minute fixture run.
"""

from __future__ import annotations

import pytest

from src.metrics.confidence_calibration import (
    CALIBRATION_MAE_THRESHOLD,
    SIGNAL_NAMES,
    compute_confidence_calibration,
)
from src.metrics.heuristic_retune import (
    DEFAULT_SHIFT_STEPS,
    default_weights,
    format_retune_proposal,
    propose_retuned_weights,
    shift_weights,
    simulate_mae,
)

BASE_WEIGHTS = {"ingredients": 0.4, "title": 0.3, "steps": 0.3}


def _sample(
    fixture_id="f",
    f1=0.5,
    source="heuristic",
    ingredients=1.0,
    title=1.0,
    steps=1.0,
    confidence=None,
):
    signals = {"ingredients": ingredients, "title": title, "steps": steps}
    if confidence is None:
        confidence = sum(BASE_WEIGHTS[k] * signals[k] for k in BASE_WEIGHTS)
    return {
        "fixture_id": fixture_id,
        "confidence": confidence,
        "ground_truth_f1": f1,
        "source": source,
        "signals": signals,
    }


# -------------------------------------------------------------------
# shift_weights
# -------------------------------------------------------------------


def test_shift_moves_weight_proportionally_off_the_other_signals():
    shifted = shift_weights(BASE_WEIGHTS, "steps", 0.5)
    # Each non-target halves; the target absorbs everything they gave up.
    assert shifted["ingredients"] == 0.2
    assert shifted["title"] == 0.15
    assert shifted["steps"] == pytest.approx(0.65)


def test_shift_preserves_the_total_exactly():
    for target in SIGNAL_NAMES:
        for fraction in DEFAULT_SHIFT_STEPS:
            shifted = shift_weights(BASE_WEIGHTS, target, fraction)
            assert sum(shifted.values()) == pytest.approx(1.0, abs=1e-9)


def test_full_shift_gives_the_target_everything():
    shifted = shift_weights(BASE_WEIGHTS, "title", 1.0)
    assert shifted == {"ingredients": 0.0, "title": 1.0, "steps": 0.0}


def test_zero_shift_is_a_no_op():
    assert shift_weights(BASE_WEIGHTS, "title", 0.0) == BASE_WEIGHTS


def test_shift_clamps_out_of_range_fractions():
    assert shift_weights(BASE_WEIGHTS, "title", -3.0) == BASE_WEIGHTS
    assert shift_weights(BASE_WEIGHTS, "title", 9.0)["title"] == 1.0


def test_unknown_target_leaves_weights_untouched():
    assert shift_weights(BASE_WEIGHTS, "nonexistent", 0.5) == BASE_WEIGHTS


def test_shift_keys_keep_the_input_order():
    assert list(shift_weights(BASE_WEIGHTS, "steps", 0.3)) == list(BASE_WEIGHTS)


# -------------------------------------------------------------------
# simulate_mae
# -------------------------------------------------------------------


def test_simulating_the_current_weights_reproduces_the_measured_mae():
    samples = [
        _sample("a", f1=0.9, steps=1.0, ingredients=1.0),
        _sample("b", f1=0.2, steps=0.0, ingredients=0.0),
    ]
    measured = compute_confidence_calibration(samples)["mae"]
    assert simulate_mae(samples, BASE_WEIGHTS)["mae"] == pytest.approx(measured)


def test_simulation_recomputes_confidence_under_new_weights():
    # Signals: ingredients=0, title=1, steps=0 -> confidence is whatever
    # weight sits on 'title'. Truth F1 is 1.0.
    sample = _sample("a", f1=1.0, ingredients=0.0, title=1.0, steps=0.0)
    assert simulate_mae([sample], BASE_WEIGHTS)["mae"] == pytest.approx(0.7)
    assert simulate_mae([sample], {"ingredients": 0.0, "title": 1.0, "steps": 0.0})[
        "mae"
    ] == pytest.approx(0.0)


def test_model_sourced_samples_keep_their_shipped_confidence():
    sample = _sample("a", f1=0.0, source="model", confidence=1.0)
    for weights in (BASE_WEIGHTS, {"ingredients": 1.0, "title": 0.0, "steps": 0.0}):
        simulated = simulate_mae([sample], weights)
        assert simulated["mae"] == pytest.approx(1.0)
        assert simulated["replayed_count"] == 0
        assert simulated["fixed_count"] == 1


def test_partial_signal_breakdown_is_not_replayed():
    # A missing signal would be read as 0.0 and fabricate an error the
    # real extractor never made — so the sample stays fixed.
    sample = _sample("a", f1=0.5)
    del sample["signals"]["steps"]
    simulated = simulate_mae([sample], BASE_WEIGHTS)
    assert simulated["replayed_count"] == 0
    assert simulated["fixed_count"] == 1


def test_simulation_clamps_confidence_into_the_unit_interval():
    sample = _sample("a", f1=0.0)
    over = {"ingredients": 5.0, "title": 5.0, "steps": 5.0}
    assert simulate_mae([sample], over)["mae"] == pytest.approx(1.0)


def test_empty_run_simulates_to_unknown_not_zero():
    assert simulate_mae([], BASE_WEIGHTS) == {
        "mae": None,
        "sample_count": 0,
        "replayed_count": 0,
        "fixed_count": 0,
    }


def test_unparseable_samples_are_dropped_before_simulation():
    simulated = simulate_mae([_sample("a", f1=0.5), "garbage", None], BASE_WEIGHTS)
    assert simulated["sample_count"] == 1


# -------------------------------------------------------------------
# propose_retuned_weights
# -------------------------------------------------------------------


def _steps_dominant_samples():
    """Confidence tracks 'steps'; the other signals are constant noise."""
    return [
        _sample("a", f1=1.0, ingredients=1.0, title=1.0, steps=1.0),
        _sample("b", f1=0.0, ingredients=1.0, title=1.0, steps=0.0),
        _sample("c", f1=1.0, ingredients=1.0, title=1.0, steps=1.0),
        _sample("d", f1=0.0, ingredients=1.0, title=1.0, steps=0.0),
    ]


def test_proposal_reaches_the_threshold_by_shifting_toward_steps():
    proposal = propose_retuned_weights(
        _steps_dominant_samples(), current_weights=BASE_WEIGHTS
    )
    assert proposal["applicable"] is True
    assert proposal["achievable"] is True
    assert proposal["shift"]["toward"] == "steps"
    assert proposal["projected_mae"] <= CALIBRATION_MAE_THRESHOLD
    assert proposal["projected_mae"] < proposal["current_mae"]


def test_proposed_weights_actually_produce_the_projected_mae():
    samples = _steps_dominant_samples()
    proposal = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    replay = simulate_mae(samples, proposal["weights"])
    assert replay["mae"] == pytest.approx(proposal["projected_mae"])


def test_proposal_prefers_the_smallest_shift_that_clears_the_gate():
    samples = _steps_dominant_samples()
    proposal = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    chosen = proposal["shift"]["fraction"]
    smaller = [
        c
        for c in proposal["candidates"]
        if c["clears"] and c["fraction"] < chosen
    ]
    assert smaller == []


def test_proposal_still_sums_to_one():
    proposal = propose_retuned_weights(
        _steps_dominant_samples(), current_weights=BASE_WEIGHTS
    )
    assert sum(proposal["weights"].values()) == pytest.approx(1.0, abs=1e-9)


def test_already_calibrated_run_proposes_no_change():
    samples = [_sample("a", f1=1.0), _sample("b", f1=1.0)]
    proposal = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    assert proposal["achievable"] is True
    assert proposal["shift"] is None
    assert proposal["weights"] == BASE_WEIGHTS
    assert "no retune needed" in proposal["reason"]


def test_all_model_sourced_run_is_not_retunable():
    samples = [
        _sample("a", f1=0.0, source="model", confidence=1.0),
        _sample("b", f1=0.0, source="model", confidence=1.0),
    ]
    proposal = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    assert proposal["applicable"] is False
    assert proposal["replayable_count"] == 0
    assert "cannot move this MAE" in proposal["reason"]
    assert proposal["weights"] == BASE_WEIGHTS


def test_empty_run_is_not_retunable():
    proposal = propose_retuned_weights([], current_weights=BASE_WEIGHTS)
    assert proposal["applicable"] is False
    assert "nothing to retune against" in proposal["reason"]


def test_unreachable_threshold_reports_best_effort_and_still_fails():
    # Confidence is pinned high by signals that are 1.0 everywhere while
    # truth F1 is 0 — no reallocation among them can help.
    samples = [
        _sample("a", f1=0.0, ingredients=1.0, title=1.0, steps=1.0),
        _sample("b", f1=0.0, ingredients=1.0, title=1.0, steps=1.0),
    ]
    proposal = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    assert proposal["applicable"] is True
    assert proposal["achievable"] is False
    assert proposal["weights"]  # a best-effort vector is still returned
    assert "no weight vector reaches MAE" in proposal["reason"]


def test_immovable_samples_are_named_in_an_unreachable_verdict():
    samples = [
        _sample("a", f1=0.0, ingredients=1.0, title=1.0, steps=1.0),
        _sample("b", f1=0.0, source="model", confidence=1.0),
    ]
    proposal = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    assert proposal["achievable"] is False
    assert proposal["immovable_count"] == 1
    assert "model-sourced and unaffected by weights" in proposal["reason"]


def test_mixed_run_retunes_only_the_heuristic_half():
    samples = _steps_dominant_samples() + [
        _sample("m", f1=0.5, source="model", confidence=0.5)
    ]
    proposal = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    assert proposal["replayable_count"] == 4
    assert proposal["immovable_count"] == 1
    assert proposal["sample_count"] == 5


def test_a_perfectly_predictive_signal_is_found_even_at_a_zero_threshold():
    # 'steps' is exactly F1 here, so a full shift onto it drives MAE to 0.
    strict = propose_retuned_weights(
        _steps_dominant_samples(), current_weights=BASE_WEIGHTS, threshold=0.0
    )
    assert strict["threshold"] == 0.0
    assert strict["achievable"] is True
    assert strict["projected_mae"] == pytest.approx(0.0)
    assert strict["weights"]["steps"] == pytest.approx(1.0)


def test_a_tighter_threshold_can_turn_an_achievable_run_unachievable():
    # 'steps' predicts F1 only loosely, so some shifts clear 0.3 while
    # nothing clears 0.02.
    samples = [
        _sample("a", f1=0.85, ingredients=1.0, title=1.0, steps=1.0),
        _sample("b", f1=0.15, ingredients=1.0, title=1.0, steps=0.0),
    ]
    assert propose_retuned_weights(
        samples, current_weights=BASE_WEIGHTS, threshold=CALIBRATION_MAE_THRESHOLD
    )["achievable"] is True
    strict = propose_retuned_weights(
        samples, current_weights=BASE_WEIGHTS, threshold=0.02
    )
    assert strict["achievable"] is False
    assert strict["threshold"] == 0.02


def test_custom_shift_steps_bound_the_search():
    proposal = propose_retuned_weights(
        _steps_dominant_samples(),
        current_weights=BASE_WEIGHTS,
        shift_steps=(0.5,),
    )
    assert {c["fraction"] for c in proposal["candidates"]} == {0.5}


def test_every_signal_is_searched_not_just_the_dominant_one():
    proposal = propose_retuned_weights(
        _steps_dominant_samples(), current_weights=BASE_WEIGHTS
    )
    assert {c["toward"] for c in proposal["candidates"]} == set(SIGNAL_NAMES)


def test_reusing_a_precomputed_calibration_result_gives_the_same_answer():
    samples = _steps_dominant_samples()
    result = compute_confidence_calibration(samples)
    reused = propose_retuned_weights(
        samples, current_weights=BASE_WEIGHTS, calibration_result=result
    )
    fresh = propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    assert reused["weights"] == fresh["weights"]
    assert reused["shift"] == fresh["shift"]


# -------------------------------------------------------------------
# Reporting
# -------------------------------------------------------------------


def test_summary_prints_the_constants_to_edit():
    proposal = propose_retuned_weights(
        _steps_dominant_samples(), current_weights=BASE_WEIGHTS
    )
    text = format_retune_proposal(proposal)
    assert "PROPOSED" in text
    assert "confidence_heuristic.py" in text
    for constant in ("_W_INGREDIENTS", "_W_TITLE", "_W_STEPS"):
        assert constant in text
    assert f"{proposal['weights']['steps']}" in text
    # Diagnosable from the run output alone: value, target, threshold.
    assert f"threshold {CALIBRATION_MAE_THRESHOLD:.2f}" in text


def test_summary_flags_a_best_effort_proposal_as_still_failing():
    samples = [
        _sample("a", f1=0.0, ingredients=1.0, title=1.0, steps=1.0),
        _sample("b", f1=0.0, ingredients=1.0, title=1.0, steps=1.0),
    ]
    text = format_retune_proposal(
        propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    )
    assert "still fails" in text


def test_summary_for_a_calibrated_run_asks_for_no_edit():
    text = format_retune_proposal(
        propose_retuned_weights(
            [_sample("a", f1=1.0), _sample("b", f1=1.0)],
            current_weights=BASE_WEIGHTS,
        )
    )
    assert "none needed" in text
    assert "_W_STEPS" not in text


def test_summary_for_an_unretunable_run_names_the_dominant_signal_only():
    samples = [
        _sample("a", f1=1.0, source="model", confidence=0.0, steps=1.0),
        _sample("b", f1=0.0, source="model", confidence=1.0, steps=0.0),
    ]
    text = format_retune_proposal(
        propose_retuned_weights(samples, current_weights=BASE_WEIGHTS)
    )
    assert "not applicable" in text
    assert "dominant signal: steps" in text


# -------------------------------------------------------------------
# Drift guard against the production module
# -------------------------------------------------------------------


def test_default_weights_track_the_shipping_heuristic():
    from utils.services.recipe_extractors import confidence_heuristic as heuristic

    assert default_weights() == {
        "ingredients": heuristic._W_INGREDIENTS,
        "title": heuristic._W_TITLE,
        "steps": heuristic._W_STEPS,
    }
    assert set(default_weights()) == set(SIGNAL_NAMES)


def test_simulation_matches_the_production_heuristic_for_the_live_weights():
    from utils.services.recipe_extractors.confidence_heuristic import (
        compute_heuristic_confidence,
    )

    recipe = {
        "name": "Banana Bread",
        "ingredients": [{"name": "flour", "quantity": 1.0}, {"name": "salt"}],
        "steps": [{"instruction": "s"}, {"instruction": "t"}],
    }
    expected = compute_heuristic_confidence(recipe)
    sample = {
        "fixture_id": "a",
        "confidence": expected,
        "ground_truth_f1": 0.0,
        "source": "heuristic",
        "signals": {"ingredients": 0.5, "title": 1.0, "steps": 2 / 3},
    }
    # MAE against F1=0 is just the confidence itself.
    assert simulate_mae([sample], default_weights())["mae"] == pytest.approx(expected)
