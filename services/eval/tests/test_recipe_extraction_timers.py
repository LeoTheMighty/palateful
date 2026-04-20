"""cmt-3 — recipe-level timer_extraction_f1 metric tests."""

import pytest

from src.config import EvalConfig
from src.evaluators.recipe_extraction_evaluator import (
    RecipeExtractionEvaluator,
    _gather_predicted_timers,
    _timer_pair_matches,
    compute_timer_f1,
)


# ---------------------------------------------------------------------
# _gather_predicted_timers
# ---------------------------------------------------------------------


def test_gather_predicted_timers_flattens_across_steps():
    actual = {
        "steps": [
            {"timers": [{"duration_minutes": 3, "label": "simmer"}]},
            {"timers": [{"duration_minutes": 10, "label": "bake"}]},
            {"timers": []},
        ]
    }
    out = _gather_predicted_timers(actual)
    assert len(out) == 2
    assert out[0]["duration_minutes"] == 3
    assert out[1]["duration_minutes"] == 10


def test_gather_predicted_timers_empty_when_only_instructions():
    """v1 simplification: no Dart-regex Python equivalent; predicted
    is empty when the extractor only emits `instructions`."""
    actual = {"instructions": "Bake 25 min then rest 10 min"}
    assert _gather_predicted_timers(actual) == []


def test_gather_predicted_timers_defensive_against_garbage():
    # Non-list steps, non-dict step entries, non-list timers.
    assert _gather_predicted_timers({"steps": "bogus"}) == []
    assert _gather_predicted_timers({"steps": [None, 42, "x"]}) == []
    assert _gather_predicted_timers({"steps": [{"timers": "bad"}]}) == []
    assert _gather_predicted_timers({"steps": [{"timers": [42, None]}]}) == []


# ---------------------------------------------------------------------
# _timer_pair_matches
# ---------------------------------------------------------------------


def test_pair_match_exact_duration_and_label():
    assert _timer_pair_matches(
        {"duration_minutes": 10, "label": "bake"},
        {"duration_minutes": 10, "label": "bake"},
    )


def test_pair_match_duration_within_20_percent():
    # 9 vs 10 = 10% slack, within ±20%.
    assert _timer_pair_matches(
        {"duration_minutes": 9, "label": "bake"},
        {"duration_minutes": 10, "label": "bake"},
    )


def test_pair_match_duration_outside_20_percent():
    # 7 vs 10 = 30% slack, outside ±20%.
    assert not _timer_pair_matches(
        {"duration_minutes": 7, "label": "bake"},
        {"duration_minutes": 10, "label": "bake"},
    )


def test_pair_match_label_similarity_floor():
    # "cook onion" vs "sauté onion" — ratio above 0.6 in practice.
    assert _timer_pair_matches(
        {"duration_minutes": 5, "label": "cook onion"},
        {"duration_minutes": 5, "label": "cook onions"},
    )


def test_pair_match_rejects_unlike_labels():
    # "boil" vs "freeze" ratio is below 0.6.
    assert not _timer_pair_matches(
        {"duration_minutes": 5, "label": "boil"},
        {"duration_minutes": 5, "label": "freeze"},
    )


def test_pair_match_rejects_non_numeric_duration():
    assert not _timer_pair_matches(
        {"duration_minutes": "25", "label": "x"},
        {"duration_minutes": 25, "label": "x"},
    )


# ---------------------------------------------------------------------
# compute_timer_f1
# ---------------------------------------------------------------------


def test_f1_perfect_match():
    actual = {
        "steps": [
            {"timers": [{"duration_minutes": 3, "label": "simmer"}]},
        ]
    }
    expected = {"expected_timers": [{"duration_minutes": 3, "label": "simmer"}]}
    assert compute_timer_f1(actual, expected) == pytest.approx(1.0)


def test_f1_both_empty_is_one():
    assert compute_timer_f1({"steps": []}, {"expected_timers": []}) == 1.0


def test_f1_predicted_empty_but_expected_populated_is_zero():
    expected = {"expected_timers": [{"duration_minutes": 3, "label": "simmer"}]}
    assert compute_timer_f1({"steps": []}, expected) == 0.0


def test_f1_expected_missing_when_fixture_hasnt_been_extended():
    """Fixtures without `expected_timers` still produce a sensible
    metric — treat as empty expected set (no regression)."""
    expected = {"name": "old fixture"}
    actual = {"steps": []}
    assert compute_timer_f1(actual, expected) == 1.0


def test_f1_ac4_three_expected_two_predicted_one_exact_one_slack():
    """AC4: 3 expected, 2 predicted, 1 exact + 1 within-slack → F1 ≈ 0.80."""
    actual = {
        "steps": [
            {
                "timers": [
                    {"duration_minutes": 10, "label": "bake"},  # exact
                    {"duration_minutes": 4, "label": "simmer"},  # 5 ±20% ok
                ]
            }
        ]
    }
    expected = {
        "expected_timers": [
            {"duration_minutes": 10, "label": "bake"},
            {"duration_minutes": 5, "label": "simmer"},
            {"duration_minutes": 15, "label": "rest"},  # unmatched
        ]
    }
    f1 = compute_timer_f1(actual, expected)
    # precision = 2/2 = 1.0; recall = 2/3 ≈ 0.667; F1 = 0.80.
    assert f1 == pytest.approx(0.80, abs=0.05)


def test_f1_greedy_one_to_one_prevents_double_counting():
    """A second duplicate predicted entry can't re-match the same
    expected slot under greedy matching."""
    actual = {
        "steps": [
            {
                "timers": [
                    {"duration_minutes": 10, "label": "bake"},
                    {"duration_minutes": 10, "label": "bake"},
                ]
            }
        ]
    }
    expected = {
        "expected_timers": [{"duration_minutes": 10, "label": "bake"}]
    }
    # 1 matched, 1 unmatched predicted. precision=0.5, recall=1.0, F1=0.667.
    assert compute_timer_f1(actual, expected) == pytest.approx(0.6667, abs=0.01)


# ---------------------------------------------------------------------
# Aggregation: _calculate_metrics surfaces timer_extraction_f1
# ---------------------------------------------------------------------


def test_calculate_metrics_includes_timer_f1_key():
    config = EvalConfig()
    evaluator = RecipeExtractionEvaluator(config)
    actual = {
        "name": "X",
        "ingredients": [],
        "steps": [{"timers": [{"duration_minutes": 10, "label": "bake"}]}],
    }
    expected = {
        "name": "X",
        "ingredients": [],
        "expected_timers": [{"duration_minutes": 10, "label": "bake"}],
    }
    metrics = evaluator._calculate_metrics(actual, expected)
    assert "timer_extraction_f1" in metrics
    assert metrics["timer_extraction_f1"] == pytest.approx(1.0)


def test_fixture_extensions_are_well_formed():
    """Simple sanity: the three fixtures we extended expose
    `expected_timers` as a list of {duration_minutes, label} dicts."""
    import json
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    for name in (
        "simple_pasta.json",
        "chicken_tikka_masala.json",
        "chocolate_chip_cookies.json",
    ):
        path = repo_root / "services/eval/fixtures/expected" / name
        data = json.loads(path.read_text())
        assert "expected_timers" in data
        assert isinstance(data["expected_timers"], list)
        for t in data["expected_timers"]:
            assert isinstance(t["duration_minutes"], int)
            assert isinstance(t["label"], str)
