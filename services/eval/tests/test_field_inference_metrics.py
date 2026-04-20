"""Tests for the efi-8 eval metrics — field_inference_accuracy + hallucination_rate."""

from __future__ import annotations

import pytest

from src.metrics.field_inference_accuracy import compute_field_inference_accuracy
from src.metrics.hallucination_rate import compute_hallucination_rate

# -------------------------------------------------------------------
# field_inference_accuracy
# -------------------------------------------------------------------


def test_numeric_within_tolerance_scores_one():
    extracted = {
        "inferred_fields": ["cook_time_minutes"],
        "cook_time_minutes": 27,
    }
    expected = {"cook_time_minutes": 30}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["cook_time_minutes"]["score"] == 1.0


def test_numeric_outside_tolerance_scores_zero():
    extracted = {
        "inferred_fields": ["cook_time_minutes"],
        "cook_time_minutes": 10,
    }
    expected = {"cook_time_minutes": 60}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["cook_time_minutes"]["score"] == 0.0


def test_servings_floor_tolerance():
    # 20% of 4 = 0.8 (rounds to 0), so the ±1 floor lets 5 count as match.
    extracted = {"inferred_fields": ["servings"], "servings": 5}
    expected = {"servings": 4}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["servings"]["score"] == 1.0


def test_exact_match_cuisine_case_insensitive():
    extracted = {"inferred_fields": ["cuisine"], "cuisine": "italian"}
    expected = {"cuisine": "Italian"}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["cuisine"]["score"] == 1.0


def test_exact_match_miss_scores_zero():
    extracted = {"inferred_fields": ["category"], "category": "Snack"}
    expected = {"category": "Dessert"}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["category"]["score"] == 0.0


def test_description_similar_above_threshold():
    extracted = {
        "inferred_fields": ["description"],
        "description": "Rich, fudgy brownies with a salted caramel swirl.",
    }
    expected = {
        "description": "Rich fudgy brownies with a salted caramel swirl.",
    }
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["description"]["score"] == 1.0


def test_description_similar_below_threshold_returns_raw_ratio():
    extracted = {
        "inferred_fields": ["description"],
        "description": "This is a salad.",
    }
    expected = {"description": "Rich, fudgy brownies with a caramel swirl."}
    out = compute_field_inference_accuracy([(extracted, expected)])
    score = out["per_field"]["description"]["score"]
    assert score is not None and 0.0 <= score < 0.6


def test_skip_when_not_flagged_inferred():
    """If the extractor didn't mark the field, it doesn't contribute."""
    extracted = {"inferred_fields": [], "cook_time_minutes": 10}
    expected = {"cook_time_minutes": 30}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["cook_time_minutes"]["sample_count"] == 0
    assert out["per_field"]["cook_time_minutes"]["score"] is None


def test_skip_when_no_ground_truth():
    """No ground-truth value → no score pair; extractor's guess ignored."""
    extracted = {
        "inferred_fields": ["cook_time_minutes"],
        "cook_time_minutes": 10,
    }
    expected: dict = {}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["per_field"]["cook_time_minutes"]["sample_count"] == 0


def test_overall_is_mean_of_per_field_means():
    """When two fields each score 1.0 and 0.0, overall = 0.5."""
    extracted = {
        "inferred_fields": ["cook_time_minutes", "cuisine"],
        "cook_time_minutes": 30,
        "cuisine": "French",
    }
    expected = {"cook_time_minutes": 30, "cuisine": "Italian"}
    out = compute_field_inference_accuracy([(extracted, expected)])
    assert out["overall"] == pytest.approx(0.5)


def test_non_dict_pair_skipped():
    """Defensive: weird inputs don't crash."""
    out = compute_field_inference_accuracy([(None, None), ("str", "str")])
    assert out["overall"] is None


# -------------------------------------------------------------------
# hallucination_rate
# -------------------------------------------------------------------


def test_rate_zero_when_no_pairs():
    out = compute_hallucination_rate([])
    assert out["rate"] == 0.0
    assert out["hallucinations"] == 0
    assert out["extractable_pairs"] == 0


def test_hallucination_counted_when_gt_and_flagged():
    extracted = {
        "inferred_fields": ["cook_time_minutes"],
        "cook_time_minutes": 30,
    }
    expected = {"cook_time_minutes": 30}
    out = compute_hallucination_rate([(extracted, expected)])
    assert out["hallucinations"] == 1
    assert out["extractable_pairs"] == 1
    assert out["rate"] == 1.0


def test_non_hallucination_when_not_flagged():
    """GT has value, extractor didn't mark as inferred → not a hallucination."""
    extracted = {"inferred_fields": [], "cook_time_minutes": 30}
    expected = {"cook_time_minutes": 30}
    out = compute_hallucination_rate([(extracted, expected)])
    assert out["hallucinations"] == 0
    assert out["extractable_pairs"] == 1
    assert out["rate"] == 0.0


def test_no_gt_not_counted():
    """Extractor guessed AND source lacked field → not a hallucination."""
    extracted = {
        "inferred_fields": ["cook_time_minutes"],
        "cook_time_minutes": 30,
    }
    expected: dict = {}
    out = compute_hallucination_rate([(extracted, expected)])
    assert out["hallucinations"] == 0
    assert out["extractable_pairs"] == 0


def test_empty_string_gt_not_counted():
    """Whitespace-only GT is treated as 'no ground truth'."""
    extracted = {"inferred_fields": ["description"], "description": "foo"}
    expected = {"description": "   "}
    out = compute_hallucination_rate([(extracted, expected)])
    assert out["extractable_pairs"] == 0


def test_per_field_breakdown():
    """Per-field counts add up correctly across pairs."""
    pairs = [
        (
            {
                "inferred_fields": ["cook_time_minutes"],
                "cook_time_minutes": 10,
            },
            {"cook_time_minutes": 30, "servings": 4},
        ),
        (
            {"inferred_fields": [], "cook_time_minutes": 30},
            {"cook_time_minutes": 30},
        ),
    ]
    out = compute_hallucination_rate(pairs)
    pf = out["per_field"]
    # cook_time_minutes: 2 extractable, 1 hallucinated → rate 0.5
    assert pf["cook_time_minutes"]["extractable"] == 2
    assert pf["cook_time_minutes"]["hallucinations"] == 1
    assert pf["cook_time_minutes"]["rate"] == pytest.approx(0.5)
    # servings: 1 extractable, 0 hallucinated → rate 0.0
    assert pf["servings"]["extractable"] == 1
    assert pf["servings"]["hallucinations"] == 0


def test_overall_rate_mixed():
    pairs = [
        (
            {
                "inferred_fields": ["cook_time_minutes", "servings"],
                "cook_time_minutes": 10,
                "servings": 4,
            },
            {"cook_time_minutes": 30, "servings": 4},
        ),
    ]
    out = compute_hallucination_rate(pairs)
    # 2 hallucinations / 2 extractable = 1.0
    assert out["rate"] == 1.0


def test_non_list_inferred_fields_ignored():
    pairs = [
        (
            {"inferred_fields": "not a list", "cook_time_minutes": 10},
            {"cook_time_minutes": 30},
        ),
    ]
    out = compute_hallucination_rate(pairs)
    assert out["hallucinations"] == 0
    # GT value still exists → extractable, just not a hallucination.
    assert out["extractable_pairs"] == 1
